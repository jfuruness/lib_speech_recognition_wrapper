import os

from pocketsphinx import get_model_path

from lib_utils import utils

tuned_path = "/etc/tuned/"

class Audio_Tuner:

    tuned_path = "/etc/tuned"
    transcription_name = "assistant.transcription"
    file_ids_name = "assistant.fileids"

    def __init__(self, tuning_phrases: list, times_to_record=1):
        """tuning phrases to be tuned to"""

        self.tuning_phrases = tuning_phrases * times_to_record
        # model path for pocket sphinx
        self.model_path = get_model_path()

    def run(self):
        self.write_files()
        input("done"))

    def write_files(self):
        self.make_tuning_dir()
        self.write_transcription_file_ids()

    def write_transcription_file_ids(self):
        with open(self.transcription_path, "w") as transcription:
            with open(self.file_ids_path, "w") as f_ids:
                for i, phrase in enumerate(self.tuning_phrases):
                    fname = self.audio_fname(i)
                    f_ids.write(fname + "\n")
                    transcription.write(f"<s> {phrase} </s> ({fname})\n")

    def make_tuning_dir(self):
        try:
            os.makedirs(self.tuned_path)
        except PermissionError as e:
            utils.run_cmds([f"sudo mkdir {self.tuned_path}",
                            f"sudo chmod -R 777 {self.tuned_path}"])
        except FileExistsError:
            pass

    def audio_fname(self, num):
        return f"{num:04}_phrase"

    @property
    def transcription_path(self):
        return os.path.join(self.tuned_path, self.transcription_name)

    @property
    def file_ids_path(self):
        return os.path.join(self.tuned_path, self.file_ids_name)
