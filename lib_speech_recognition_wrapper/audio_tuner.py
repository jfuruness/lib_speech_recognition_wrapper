import os
from multiprocessing import cpu_count, Queue

from pathos.multiprocessing import ProcessPool
from pocketsphinx import get_model_path
import pyaudio
import wave

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
        self.record_files()
        input("done")

    def write_files(self):
        self.make_tuning_dir()
        self.write_transcription_file_ids()

    def record_files(self):
        for phrase, fname in self.phrase_iter():
            self.record_phrase(phrase, fname)

    def write_transcription_file_ids(self):
        with open(self.transcription_path, "w") as transcription:
            with open(self.file_ids_path, "w") as f_ids:
                for phrase, fname in self.phrase_iter():
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

    def record_phrase(self, phrase, fname):
        satisfied = False
        while not satisfied:
            q = Queue
            # spawn process that records audio
            with utils.Pool(thread=2, multiplier=0, name="record pool") as p:
                input(f"Get ready to record: {phrase}, hit enter when ready")
                pool.apipe(self.audio_recording_process, fname, q)
                input(f"Go! Record: {phrase} then hit enter!")
                q.put("done")
            retry_key = "n"
            ans = input(f"Satisfied? enter {retry_key} to retry")
            if retry_key not in ans.lower():
                satisfied = True

    def audio_recording_process(self, fname, q):
        # TODO: refactor this to include this stuff as class attrs of wrapper
        stream, p, chunk_size = Speech_Recognition_Wrapper.start_audio(self)
        frames = []
        while q.empty():
            frames.append(stream.read(chunk_size))
        frames.append(stream.read(chunk_size))
        stream.close()
        p.terminate()

        with wave.open(fname, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16)
            wf.setframerate(16000)
            wf.writeframes(b''.join(frames))

    def phrase_iter(self):
        """Returns phrase and fnames"""

        for i, phrase in enumerate(self.tuning_phrases):
            yield phrase, self.audio_fname(i)

    def audio_fname(self, num):
        return f"{num:04}_phrase"

    @property
    def transcription_path(self):
        return os.path.join(self.tuned_path, self.transcription_name)

    @property
    def file_ids_path(self):
        return os.path.join(self.tuned_path, self.file_ids_name)
