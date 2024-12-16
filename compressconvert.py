import os
import subprocess
import sys
import tempfile
import configparser
from PIL import Image
import ffmpeg
import subprocess
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QFileDialog, QProgressBar, QCheckBox,
    QTextEdit, QSlider, QComboBox, QMessageBox, QScrollArea, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QIcon


# Function to check if FFmpeg is installed
def check_ffmpeg_installed():
    try:
        subprocess.run(['ffmpeg', '-version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise EnvironmentError("FFmpeg is not installed or not found in system PATH.")


# Image Compression Function
def compress_image(input_path, output_path, target_percentage=50, output_format='jpg', progress_callback=None, error_log_callback=None):
    try:
        with Image.open(input_path) as img:
            output_format = output_format.lower()

            if output_format in ['jpg', 'jpeg']:
                if img.mode in ('RGBA', 'P'):
                    img = img.convert("RGB")
                quality = int(95 * (target_percentage / 100))
                quality = max(5, min(quality, 95))
                img.save(output_path, format='JPEG', quality=quality)
            elif output_format == 'png':
                if img.mode in ('RGBA', 'P'):
                    img = img.convert("RGBA")
                else:
                    img = img.convert("RGB")
                img.save(output_path, format='PNG', optimize=True)
            elif output_format == 'webp':
                img.save(output_path, format='WEBP', quality=int(100 * (target_percentage / 100)))
            else:
                raise ValueError(f"Unsupported output format: {output_format}")

            if progress_callback:
                progress_callback(1.0)

    except Exception as e:
        if error_log_callback:
            error_log_callback(f"Image Compression Error for {os.path.basename(input_path)}: {str(e)}")
        raise e


# Video Compression Function
def compress_video(input_path, output_path, target_percentage=50, output_format='mp4', high_quality_audio=True, progress_callback=None, error_log_callback=None):
    try:
        probe = ffmpeg.probe(input_path)
    except ffmpeg.Error as e:
        error_message = f"FFmpeg probe error for {os.path.basename(input_path)}: {e.stderr.decode()}"
        if error_log_callback:
            error_log_callback(error_message)
        raise ValueError(error_message)

    duration_str = probe['format'].get('duration', None)
    if duration_str is None or duration_str == 'N/A':
        error_message = f"Cannot determine duration of video file: {input_path}"
        if error_log_callback:
            error_log_callback(error_message)
        raise ValueError(error_message)

    try:
        duration = float(duration_str)
    except ValueError:
        error_message = f"Invalid duration value '{duration_str}' for file: {input_path}"
        if error_log_callback:
            error_log_callback(error_message)
        raise ValueError(error_message)

    original_size = os.path.getsize(input_path)
    target_size = original_size * (target_percentage / 100)

    audio_bitrate = 256000 if high_quality_audio else 64000
    total_bitrate = (target_size * 8) / duration

    min_video_bitrate = 100000
    min_total_bitrate = audio_bitrate + min_video_bitrate
    total_bitrate = max(total_bitrate, min_total_bitrate)

    video_bitrate = total_bitrate - audio_bitrate
    max_video_bitrate = 50000000
    video_bitrate = min(video_bitrate, max_video_bitrate)
    subprocess.run(['ffmpeg', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    command = [
        'ffmpeg',
        '-i', input_path,
        '-b:v', str(int(video_bitrate)),
        '-b:a', str(int(audio_bitrate)),
        '-c:a', 'aac',
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-f', output_format,
        '-y',
        '-progress', 'pipe:1',
        output_path
    ]

    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

        while True:
            line = process.stdout.readline()
            if line == '' and process.poll() is not None:
                break
            if 'out_time_ms=' in line:
                value = line.strip().split('=')[1]
                try:
                    out_time_ms = int(value)
                    progress = min(out_time_ms / (duration * 1000000), 1.0)
                    if progress_callback:
                        progress_callback(progress)
                except ValueError:
                    error_message = f"Non-integer out_time_ms encountered: '{value}' in line: {line.strip()}"
                    if error_log_callback:
                        error_log_callback(error_message)
                    continue

        process.wait()

        if process.returncode != 0:
            error_message = f"FFmpeg failed with return code {process.returncode} for file: {os.path.basename(input_path)}"
            if error_log_callback:
                error_log_callback(error_message)
            raise RuntimeError(error_message)
    except Exception as e:
        if error_log_callback:
            error_log_callback(f"Video Compression Error for {os.path.basename(input_path)}: {str(e)}")
        raise e


# Audio Extraction Function
def extract_audio(input_path, output_path, bitrate=320, progress_callback=None, error_log_callback=None):
    try:
        probe = ffmpeg.probe(input_path)
        duration_str = probe['format'].get('duration', None)
        if duration_str is None or duration_str == 'N/A':
            error_message = f"Cannot determine duration of video file: {input_path}"
            if error_log_callback:
                error_log_callback(error_message)
            raise ValueError(error_message)
        try:
            duration = float(duration_str)
        except ValueError:
            error_message = f"Invalid duration value '{duration_str}' for file: {input_path}"
            if error_log_callback:
                error_log_callback(error_message)
            raise ValueError(error_message)

        command = [
            'ffmpeg',
            '-i', input_path,
            '-vn',
            '-ar', '44100',
            '-ac', '2',
            '-b:a', f'{bitrate}k',
            '-f', 'mp3',
            '-y',
            '-progress', 'pipe:1',
            output_path
        ]

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

        while True:
            line = process.stdout.readline()
            if line == '' and process.poll() is not None:
                break
            if 'out_time_ms=' in line:
                value = line.strip().split('=')[1]
                try:
                    out_time_ms = int(value)
                    progress = min(out_time_ms / (duration * 1000000), 1.0)
                    if progress_callback:
                        progress_callback(progress)
                except ValueError:
                    error_message = f"Non-integer out_time_ms encountered: '{value}' in line: {line.strip()}"
                    if error_log_callback:
                        error_log_callback(error_message)
                    continue

        process.wait()

        if process.returncode != 0:
            error_message = f"FFmpeg failed with return code {process.returncode} for file: {os.path.basename(input_path)}"
            if error_log_callback:
                error_log_callback(error_message)
            raise RuntimeError(error_message)
    except Exception as e:
        if error_log_callback:
            error_log_callback(f"Audio Extraction Error for {os.path.basename(input_path)}: {str(e)}")
        raise e


# Audio Compression Function
def compress_audio(input_path, output_path, bitrate=128, output_format='mp3', progress_callback=None, error_log_callback=None):
    try:
        probe = ffmpeg.probe(input_path)
    except ffmpeg.Error as e:
        error_message = f"FFmpeg probe error for {os.path.basename(input_path)}: {e.stderr.decode()}"
        if error_log_callback:
            error_log_callback(error_message)
        raise ValueError(error_message)

    duration_str = probe['format'].get('duration', None)
    if duration_str is None or duration_str == 'N/A':
        error_message = f"Cannot determine duration of audio file: {input_path}"
        if error_log_callback:
            error_log_callback(error_message)
        raise ValueError(error_message)

    try:
        duration = float(duration_str)
    except ValueError:
        error_message = f"Invalid duration value '{duration_str}' for file: {input_path}"
        if error_log_callback:
            error_log_callback(error_message)
        raise ValueError(error_message)

    audio_codec = 'libmp3lame' if output_format.lower() == 'mp3' else 'aac'

    command = [
        'ffmpeg',
        '-i', input_path,
        '-b:a', f'{bitrate}k',
        '-c:a', audio_codec,
        '-f', output_format,
        '-y',
        '-progress', 'pipe:1',
        output_path
    ]

    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

        while True:
            line = process.stdout.readline()
            if line == '' and process.poll() is not None:
                break
            if 'out_time_ms=' in line:
                value = line.strip().split('=')[1]
                try:
                    out_time_ms = int(value)
                    progress = min(out_time_ms / (duration * 1000000), 1.0)
                    if progress_callback:
                        progress_callback(progress)
                except ValueError:
                    error_message = f"Non-integer out_time_ms encountered: '{value}' in line: {line.strip()}"
                    if error_log_callback:
                        error_log_callback(error_message)
                    continue

        process.wait()

        if process.returncode != 0:
            error_message = f"FFmpeg failed with return code {process.returncode} for file: {os.path.basename(input_path)}"
            if error_log_callback:
                error_log_callback(error_message)
            raise RuntimeError(error_message)
    except Exception as e:
        if error_log_callback:
            error_log_callback(f"Audio Compression Error for {os.path.basename(input_path)}: {str(e)}")
        raise e


# Function to open the output folder
def open_folder(folder_path):
    if os.name == 'nt':
        os.startfile(folder_path)
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', folder_path])
    else:
        subprocess.Popen(['xdg-open', folder_path])


# Worker Thread for Compression
class CompressionWorker(QThread):
    progress_signal = Signal(float)
    status_signal = Signal(str)
    error_signal = Signal(str)
    completed_signal = Signal(bool)

    def __init__(self, files_to_process, options):
        super().__init__()
        self.files_to_process = files_to_process
        self.options = options
        self._is_interrupted = False

    def run(self):
        try:
            success = True
            total_files = len(self.files_to_process)
            processed_files = 0

            self.status_signal.emit("Starting compression...")

            for input_path, output_path in self.files_to_process:
                if self._is_interrupted:
                    self.status_signal.emit("Compression interrupted.")
                    self.completed_signal.emit(False)
                    return

                try:
                    def file_progress_callback(progress):
                        overall_progress = ((processed_files + progress) / total_files)
                        self.progress_signal.emit(overall_progress)

                    if input_path.lower().endswith(('png', 'jpg', 'jpeg', 'webp')):
                        output_format = os.path.splitext(output_path)[1][1:]
                        compress_image(
                            input_path,
                            output_path,
                            target_percentage=self.options['image_size_percentage'],
                            output_format=output_format,
                            progress_callback=file_progress_callback,
                            error_log_callback=self.error_signal.emit
                        )
                    elif input_path.lower().endswith(('mp4', 'mov', 'avi', 'mkv', 'mp3')):
                        output_format = os.path.splitext(output_path)[1][1:]
                        if output_format.lower() == 'mp3':
                            extract_audio(
                                input_path,
                                output_path,
                                bitrate=int(self.options['audio_bitrate']),
                                progress_callback=file_progress_callback,
                                error_log_callback=self.error_signal.emit
                            )
                        else:
                            compress_video(
                                input_path,
                                output_path,
                                target_percentage=self.options['video_size_percentage'],
                                output_format=output_format,
                                high_quality_audio=self.options['high_quality_audio'],
                                progress_callback=file_progress_callback,
                                error_log_callback=self.error_signal.emit
                            )
                    elif input_path.lower().endswith(('mp3', 'wav', 'flac', 'aac', 'ogg', 'm4a')):
                        output_format = os.path.splitext(output_path)[1][1:]
                        compress_audio(
                            input_path,
                            output_path,
                            bitrate=int(self.options['audio_bitrate']),
                            output_format=output_format,
                            progress_callback=file_progress_callback,
                            error_log_callback=self.error_signal.emit
                        )
                    else:
                        self.status_signal.emit(f"Unsupported file type: {input_path}")
                        self.error_signal.emit(f"Unsupported file type: {input_path}")
                        continue

                    processed_files += 1
                    self.status_signal.emit(f"Compressed {processed_files}/{total_files} files.")
                    self.error_signal.emit(f"Successfully compressed: {os.path.basename(input_path)}")

                except ValueError as e:
                    self.status_signal.emit(f"Error processing {os.path.basename(input_path)}.")
                    self.error_signal.emit(f"Error processing {os.path.basename(input_path)}: {str(e)}")
                    success = False
                except Exception as e:
                    self.status_signal.emit(f"Error processing {os.path.basename(input_path)}.")
                    self.error_signal.emit(f"Error processing {os.path.basename(input_path)}: {str(e)}")
                    success = False

            if success:
                self.status_signal.emit("Compression complete!")
                self.progress_signal.emit(1.0)
                self.error_signal.emit("Compression completed successfully.")
                if self.options['output_folder']:
                    open_folder(self.options['output_folder'])
            else:
                self.status_signal.emit("Compression completed with errors.")
                self.error_signal.emit("Compression completed with some errors.")

            self.completed_signal.emit(success)

        except Exception as e:
            self.status_signal.emit("An error occurred during compression.")
            self.error_signal.emit(f"An unexpected error occurred: {str(e)}")
            self.completed_signal.emit(False)

    def interrupt(self):
        self._is_interrupted = True


# Custom QLabel for Drag and Drop
class DropLabel(QLabel):
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("'Drag and drop your folder or files here'")
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #2b2b2b;
                color: #ffffff;
                background-color: #2b2b2b;
                font-size: 14px;
                border-radius: 10px;
            }
        """)
        self.setFixedSize(400, 80)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        paths = [url.toLocalFile() for url in urls]
        self.files_dropped.emit(paths)


# Main Application Window
class MediaCompressorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Media Compressor")
        self.setGeometry(100, 100, 500, 600)  # Increased width for better layout
        self.setWindowIcon(QIcon("bottomlogo.png"))  # Ensure the icon exists

        # Initialize configuration
        self.config = configparser.ConfigParser()
        self.config_file = self.get_config_file_path()
        self.load_config()

        # Main Widget
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)

        # Main Layout
        self.main_layout = QVBoxLayout()
        self.main_widget.setLayout(self.main_layout)

        # Drag and Drop Label centered
        self.dnd_layout = QHBoxLayout()
        self.dnd_layout.addStretch()
        self.dnd_label = DropLabel()
        self.dnd_layout.addWidget(self.dnd_label)
        self.dnd_layout.addStretch()
        self.main_layout.addLayout(self.dnd_layout)

        self.dnd_label.files_dropped.connect(self.handle_dropped_files)

        # Buttons Layout (Centered)
        self.button_layout = QHBoxLayout()
        self.main_layout.addLayout(self.button_layout)

        self.button_layout.addStretch()  # Add stretch before the buttons

        # Select Files Button
        self.select_button = QPushButton("Select Files")
        self.select_button.clicked.connect(self.select_files)
        self.button_layout.addWidget(self.select_button)

        # Clear Selection Button
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_selection)
        self.button_layout.addWidget(self.clear_button)

        # Select Output Folder Button
        self.select_output_button = QPushButton("Select Output Folder")
        self.select_output_button.clicked.connect(self.select_output_folder)
        self.button_layout.addWidget(self.select_output_button)

        self.button_layout.addStretch()  # Add stretch after the buttons


        # Options Layout
        self.options_layout = QHBoxLayout()
        self.main_layout.addLayout(self.options_layout)

        # Audio Options on the Left
        self.audio_layout = QVBoxLayout()
        self.options_layout.addLayout(self.audio_layout)

        self.audio_group_label = QLabel("Audio Options")
        self.audio_group_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.audio_layout.addWidget(self.audio_group_label)

        # Audio Format
        self.audio_format_layout = QHBoxLayout()
        self.audio_layout.addLayout(self.audio_format_layout)

        self.audio_format_label = QLabel("Format:")
        self.audio_format_layout.addWidget(self.audio_format_label)

        self.audio_format_combo = QComboBox()
        self.audio_format_combo.addItems(['mp3', 'wav', 'flac', 'aac', 'ogg', 'm4a'])
        self.audio_format_layout.addWidget(self.audio_format_combo)

        # Audio Bitrate
        self.audio_bitrate_layout = QHBoxLayout()
        self.audio_layout.addLayout(self.audio_bitrate_layout)

        self.audio_bitrate_label = QLabel("Bitrate:")
        self.audio_bitrate_layout.addWidget(self.audio_bitrate_label)

        self.audio_bitrate_combo = QComboBox()
        self.audio_bitrate_combo.addItems(['128', '256', '320'])
        self.audio_bitrate_combo.setCurrentText("256")  # Set default audio bitrate to 256
        self.audio_bitrate_layout.addWidget(self.audio_bitrate_combo)


        # High Quality Audio Checkbox
        self.high_quality_audio_checkbox = QCheckBox("High Quality Audio for Videos")
        self.high_quality_audio_checkbox.setChecked(True)  # Set checkbox active by default
        self.high_quality_audio_checkbox.stateChanged.connect(self.toggle_audio_quality)  # Connect to slot
        self.audio_layout.addWidget(self.high_quality_audio_checkbox)


        # Spacer to separate audio options from other sections
        self.audio_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Image Options on the Right
        self.image_video_layout = QVBoxLayout()
        self.options_layout.addLayout(self.image_video_layout)

        # Image Options
        self.image_layout = QVBoxLayout()
        self.image_video_layout.addLayout(self.image_layout)

        self.image_group_label = QLabel("Image Options")
        self.image_group_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.image_layout.addWidget(self.image_group_label)

        # Image Format
        self.image_format_layout = QHBoxLayout()
        self.image_layout.addLayout(self.image_format_layout)

        self.image_format_label = QLabel("Format:")
        self.image_format_layout.addWidget(self.image_format_label)

        self.image_format_combo = QComboBox()
        self.image_format_combo.addItems(['jpg', 'jpeg', 'png', 'webp'])
        self.image_format_layout.addWidget(self.image_format_combo)

        # Image Size Slider
        self.image_size_layout = QHBoxLayout()
        self.image_layout.addLayout(self.image_size_layout)

        self.image_size_label = QLabel("Size: 50%")
        self.image_size_layout.addWidget(self.image_size_label)

        self.image_size_slider = QSlider(Qt.Horizontal)
        self.image_size_slider.setRange(5, 100)
        self.image_size_slider.setValue(50)
        self.image_size_slider.setTickInterval(5)
        self.image_size_slider.valueChanged.connect(self.update_image_size_label)
        self.image_size_layout.addWidget(self.image_size_slider)

        # Video Options
        self.video_layout = QVBoxLayout()
        self.image_video_layout.addLayout(self.video_layout)

        self.video_group_label = QLabel("Video Options")
        self.video_group_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.video_layout.addWidget(self.video_group_label)

        # Video Format
        self.video_format_layout = QHBoxLayout()
        self.video_layout.addLayout(self.video_format_layout)

        self.video_format_label = QLabel("Format:")
        self.video_format_layout.addWidget(self.video_format_label)

        self.video_format_combo = QComboBox()
        self.video_format_combo.addItems(['mp4', 'mkv', 'avi', 'mov', 'mp3'])  # 'mp3' for audio extraction
        self.video_format_layout.addWidget(self.video_format_combo)

        # Video Size Slider
        self.video_size_layout = QHBoxLayout()
        self.video_layout.addLayout(self.video_size_layout)

        self.video_size_label = QLabel("Size: 50%")
        self.video_size_layout.addWidget(self.video_size_label)

        self.video_size_slider = QSlider(Qt.Horizontal)
        self.video_size_slider.setRange(5, 100)
        self.video_size_slider.setValue(50)
        self.video_size_slider.setTickInterval(5)
        self.video_size_slider.valueChanged.connect(self.update_video_size_label)
        self.video_size_layout.addWidget(self.video_size_slider)

        # Spacer to push options to the top
        self.image_video_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Create New Folder Checkbox
        self.create_folder_checkbox = QCheckBox("Create a New Folder for Exported Files")
        self.main_layout.addWidget(self.create_folder_checkbox)

        # Export Button
        self.export_button = QPushButton("Compress/Convert Media")
        self.export_button.clicked.connect(self.export_compressed)
        self.main_layout.addWidget(self.export_button)

        # Status Label
        self.status_label = QLabel("")
        self.main_layout.addWidget(self.status_label)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.main_layout.addWidget(self.progress_bar)

        # Error Log
        self.error_log = QTextEdit()
        self.error_log.setReadOnly(True)
        self.error_log.setStyleSheet("""
            QTextEdit {
                background-color: #1f1f1f;
                color: red;
                border: 1px solid #2b2b2b;
            }
        """)
        self.main_layout.addWidget(self.error_log)

        # Initialize variables
        self.input_files = []
        self.output_folder = self.config.get('Settings', 'output_folder', fallback=None)
        if self.output_folder and os.path.isdir(self.output_folder):
            self.status_label.setText(f"Output folder selected: {self.output_folder}")

        # Thread Placeholder
        self.worker = None


    @Slot(int)
    def toggle_audio_quality(self, state):
        """
        Adjust the audio bitrate based on the High-Quality Audio checkbox state.
        """
        if state == Qt.Checked:  # High-Quality Audio enabled
            self.audio_bitrate_combo.setCurrentText("320")
            self.audio_bitrate_combo.setEnabled(False)  # Disable manual selection
        else:  # High-Quality Audio disabled
            self.audio_bitrate_combo.setCurrentText("128")
            self.audio_bitrate_combo.setEnabled(True)  # Allow manual selection
            self.high_quality_audio_checkbox.setToolTip("Enable high-quality audio (320 kbps). Uncheck to use lower bitrate.")
            self.audio_bitrate_combo.setToolTip("Manually select audio bitrate when high-quality audio is disabled.")


    def get_config_file_path(self):
        if sys.platform.startswith('win'):
            config_dir = os.path.join(os.getenv('APPDATA'), 'MediaCompressor')
        elif sys.platform.startswith('darwin'):
            config_dir = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'MediaCompressor')
        else:
            config_dir = os.path.join(os.path.expanduser('~'), '.config', 'MediaCompressor')
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, 'settings.ini')

    def load_config(self):
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
        else:
            self.config['Settings'] = {}
            with open(self.config_file, 'w') as f:
                self.config.write(f)

    def save_config(self):
        self.config['Settings']['output_folder'] = self.output_folder if self.output_folder else ''
        with open(self.config_file, 'w') as f:
            self.config.write(f)

    def handle_dropped_files(self, paths):
        new_files = []
        for path in paths:
            if os.path.isdir(path):
                for root_dir, _, files in os.walk(path):
                    for file in files:
                        file_path = os.path.join(root_dir, file)
                        if self.is_supported_file(file_path):
                            new_files.append(file_path)
            elif os.path.isfile(path) and self.is_supported_file(path):
                new_files.append(path)

        if new_files:
            self.input_files.extend(new_files)
            self.input_files = list(set(self.input_files))  # Remove duplicates
            self.dnd_label.setText(f"{len(self.input_files)} file(s) selected")
        else:
            self.dnd_label.setText("No supported files found.")

    def select_files(self):
        file_dialog = QFileDialog(self, "Select Files", "",
                                  "Supported files (*.png *.jpg *.jpeg *.webp *.mp4 *.mov *.avi *.mkv *.mp3 *.wav *.flac *.aac *.ogg *.m4a);;All files (*.*)")
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.input_files.extend(selected_files)
                self.input_files = list(set(self.input_files))  # Remove duplicates
                self.dnd_label.setText(f"{len(self.input_files)} file(s) selected")

    def clear_selection(self):
        self.input_files = []
        self.dnd_label.setText("'Drag and drop your folder or files here'")
        self.log_error("Selection cleared.")

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder = folder
            self.status_label.setText(f"Output folder selected: {self.output_folder}")
            self.log_error(f"Output folder selected: {self.output_folder}")
            self.save_config()

    def update_image_size_label(self, value):
        self.image_size_label.setText(f"Size: {value}%")

    def update_video_size_label(self, value):
        self.video_size_label.setText(f"Size: {value}%")

    def export_compressed(self):
        if not self.input_files:
            self.update_status("Please select files or folders to compress.")
            self.log_error("No files selected for compression.")
            return

        if not self.output_folder:
            self.update_status("Please select an output folder.")
            self.log_error("No output folder selected.")
            return

        # Create new folder if checkbox is checked
        output_folder = self.output_folder
        if self.create_folder_checkbox.isChecked():
            new_folder_name, ok = QFileDialog.getText(self, "New Folder Name", "Enter a name for the new export folder:")
            if ok and new_folder_name:
                output_folder = os.path.join(self.output_folder, new_folder_name)
                try:
                    os.makedirs(output_folder, exist_ok=True)
                    self.log_error(f"Created new folder: {output_folder}")
                except Exception as e:
                    self.update_status(f"Failed to create folder: {new_folder_name}")
                    self.log_error(f"Failed to create folder: {new_folder_name}. Error: {str(e)}")
                    return
            else:
                self.update_status("Folder creation cancelled.")
                self.log_error("Folder creation was cancelled by the user.")
                return

        # Prepare output paths
        files_to_process = []
        for file_path in self.input_files:
            try:
                if file_path.lower().endswith(('png', 'jpg', 'jpeg', 'webp')):
                    default_extension = '.' + self.image_format_combo.currentText()
                elif file_path.lower().endswith(('mp4', 'mov', 'avi', 'mkv', 'mp3')):
                    default_extension = '.' + self.video_format_combo.currentText()
                elif file_path.lower().endswith(('mp3', 'wav', 'flac', 'aac', 'ogg', 'm4a')):
                    default_extension = '.' + self.audio_format_combo.currentText()
                else:
                    continue

                base_name = os.path.basename(file_path)
                name, _ = os.path.splitext(base_name)
                suggested_name = f"{name}_compressed{default_extension}"

                output_path = os.path.join(output_folder, suggested_name)
                files_to_process.append((file_path, output_path))

            except Exception as e:
                self.update_status(f"Error preparing {file_path}: {str(e)}")
                self.log_error(f"Error preparing {file_path}: {str(e)}")

        if not files_to_process:
            self.update_status("No files to process.")
            self.log_error("No valid files to process after preparation.")
            return

        # Disable UI elements during processing
        self.export_button.setEnabled(False)
        self.select_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.select_output_button.setEnabled(False)

        # Prepare options
        options = {
            'image_size_percentage': self.image_size_slider.value(),
            'video_size_percentage': self.video_size_slider.value(),
            'audio_bitrate': self.audio_bitrate_combo.currentText(),  # Dynamically fetched bitrate
            'output_folder': output_folder,
            'high_quality_audio': self.high_quality_audio_checkbox.isChecked()
        }


        # Start worker thread
        self.worker = CompressionWorker(files_to_process, options)
        self.worker.progress_signal.connect(self.update_progress_bar)
        self.worker.status_signal.connect(self.update_status)
        self.worker.error_signal.connect(self.log_error)
        self.worker.completed_signal.connect(self.compression_finished)
        self.worker.start()

    @Slot(float)
    def update_progress_bar(self, value):
        self.progress_bar.setValue(int(value * 100))

    @Slot(str)
    def update_status(self, message):
        self.status_label.setText(message)

    @Slot(str)
    def log_error(self, message):
        self.error_log.append(message)

    @Slot(bool)
    def compression_finished(self, success):
        # Re-enable UI elements
        self.export_button.setEnabled(True)
        self.select_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.select_output_button.setEnabled(True)

        if success:
            QMessageBox.information(self, "Success", "Compression completed successfully!")
        else:
            QMessageBox.warning(self, "Completed with Errors", "Compression completed with some errors.")

    def is_supported_file(self, file_path):
        supported_extensions = (
            '.png', '.jpg', '.jpeg', '.webp',
            '.mp4', '.mov', '.avi', '.mkv',
            '.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'
        )
        return file_path.lower().endswith(supported_extensions)


def main():
    try:
        check_ffmpeg_installed()
    except EnvironmentError as e:
        app = QApplication(sys.argv)
        QMessageBox.critical(None, "FFmpeg Not Found", str(e))
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Optional: set a consistent style

    window = MediaCompressorApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
