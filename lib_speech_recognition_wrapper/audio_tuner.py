import os
import logging
from multiprocessing import Manager

from pathos.multiprocessing import ProcessPool
from pocketsphinx import get_model_path
import pyaudio
import tarfile
import wave

from lib_utils import utils

from . import speech_recognition_wrapper as sr

tuned_path = "/etc/tuned/"

class Audio_Tuner:

    tuned_path = "/etc/tuned"
    transcription_name = "assistant.transcription"
    file_ids_name = "assistant.fileids"

    def __init__(self, tuning_phrases: list, times_to_record=1, test=False):
        """tuning phrases to be tuned to"""

        self.model_path = get_model_path()
        self.tuning_phrases = tuning_phrases * times_to_record
        if test:
            self.tuning_phrases = self.tuning_phrases[:1]
        # model path for pocket sphinx
        self.model_path = get_model_path()

    def run(self):
        self.write_files()
        self.record_files()
        self.copy_files()
        self.install_sphinx_base()
        self.run_sphinx_fe()
        self.download_proper_en()
        input("wait")        

    def write_files(self):
        utils.delete_paths(self.tuned_path)
        utils.makedirs(self.tuned_path)
        self.write_transcription_file_ids()

    def record_files(self):
        for phrase, fname in self.phrase_iter():
            self.record_phrase(phrase, fname)
        input(f"check wave files in {self.tuned_path}, then hit enter")

    def copy_files(self):
        # Using bash instead of python to closely follow directions on
        # https://cmusphinx.github.io/wiki/tutorialadapt/
        input(self.model_path)
        for _dir in ["en-us",
                     "cmudict-en-us.dict",
                     "en-us.lm.bin"]:
            path = os.path.join(self.model_path, _dir)
            utils.run_cmds(f"cp -a {path} {self.tuned_path}")

    def install_sphinx_base(self):
        logging.info("Downloading sphinx base. This may take a minute")
        # https://bangladroid.wordpress.com/2017/02/16/installing-cmu-sphinx-on-ubuntu/
        utils.run_cmds("sudo apt-get install -y gcc automake autoconf libtool "
                       "bison swig python-dev libpulse-dev")
        sphinx_path = os.path.join(self.tuned_path, "sphinx-src")
        utils.makedirs(sphinx_path, remake=True)
        url = "https://github.com/cmusphinx/sphinxbase.git"
        # sudo is used on the first command to ensure it's use
        utils.run_cmds([f"sudo ls ",
                        f"cd {sphinx_path}",
                        f"git clone {url}",
                        "cd sphinxbase",
                        "./autogen.sh",
                        "make",
                        "sudo make install",
                        f"cp src/sphinx_fe/sphinx_fe {self.tuned_path}"])

    def run_sphinx_fe(self):
        utils.run_cmds([f"cd {self.tuned_path}",
                       (f"sphinx_fe -argfile en-us/feat.params "
                        f"-samprate 16000 -c {self.file_ids_path} "
                        "-di . -do . -ei wav -eo mfc -mswav yes")])

    def download_proper_en(self):
        url = ("https://phoenixnap.dl.sourceforge.net/project/cmusphinx/"
               "Acoustic%20and%20Language%20Models/US%20English/"
               "cmusphinx-en-us-5.2.tar.gz")
        path = os.path.join(self.tuned_path, "larger_sphinx")
        utils.download_file(url, path)
        with tarfile.open(path) as f:
            old_en_us_path = os.path.join(self.tuned_path, "en-us")
            utils.delete_paths(old_en_us_path)
            f.extractall(old_en_us_path)

    def write_transcription_file_ids(self):
        with open(self.transcription_path, "w") as transcription:
            with open(self.file_ids_path, "w") as f_ids:
                for phrase, fname in self.phrase_iter():
                    f_ids.write(fname + "\n")
                    transcription.write(f"<s> {phrase} </s> ({fname})\n")

    def record_phrase(self, phrase, fname):
        satisfied = False
        while not satisfied:
            # spawn process that records audio
            with utils.Pool(4, 0, "record pool") as pool:
                input(f"Get ready to record: {phrase}, hit enter when ready")
                m = Manager()
                q = m.Queue()
                pool.apipe(self.audio_recording_process, fname, q)
                input()
                q.put("done")
            retry_key = "n"
            ans = input(f"Satisfied? enter {retry_key} to retry")
            if retry_key not in ans.lower():
                satisfied = True

    def audio_recording_process(self, fname, q):
        # TODO: refactor this to include this stuff as class attrs of wrapper
        stream, p, chunk_size = sr.Speech_Recognition_Wrapper.start_audio(self)
        utils.write_to_stdout("Ready! Record, then hit enter!")
        frames = []
        while q.empty():
            frames.append(stream.read(chunk_size))
        frames.append(stream.read(chunk_size))
        stream.close()
        p.terminate()

        with wave.open(self.audio_path(fname) + ".wav", 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(16000)
            wf.writeframes(b''.join(frames))


    def phrase_iter(self):
        """Returns phrase and fnames"""

        for i, phrase in enumerate(self.tuning_phrases):
            yield phrase, self.audio_fname(i)

    def audio_path(self, fname):
        return os.path.join(self.tuned_path, fname)

    def audio_fname(self, num):
        return f"{num:04}_phrase"

    @property
    def transcription_path(self):
        return os.path.join(self.tuned_path, self.transcription_name)

    @property
    def file_ids_path(self):
        return os.path.join(self.tuned_path, self.file_ids_name)
