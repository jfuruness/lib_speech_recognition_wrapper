from datetime import datetime
import re
import os
import logging
from multiprocessing import Manager, cpu_count
from random import shuffle

from pathos.multiprocessing import ProcessPool
from pocketsphinx import get_model_path
import pyaudio
import tarfile
from shutil import copyfile
import wave

from lib_utils.helper_funcs import Pool, run_cmds
from lib_utils.print_funcs import write_to_stdout
from lib_utils.file_funcs import makedirs, delete_paths, download_file

from . import speech_recognition_wrapper as sr

tuned_path = "/etc/tuned/"

class Audio_Tuner:

    tuned_path = "/etc/tuned"
    audio_path  ="/etc/audio"
    transcription_name = "assistant.transcription"
    file_ids_name = "assistant.fileids"
    test_transcription_name = "test.transcription"
    test_file_ids_name = "test.fileids"

    def __init__(self, tuning_phrases: list, times_to_record=1, test=False):
        """tuning phrases to be tuned to"""

        self.session_id = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        self.username = input("User name: ").lower()
        self.session_id += f"_{self.username}_"
        self.model_path = get_model_path()
        self.tuning_phrases = tuning_phrases * times_to_record
        if test:
            shuffle(self.tuning_phrases)
            self.tuning_phrases = self.tuning_phrases[:1]
        # model path for pocket sphinx
        self.model_path = get_model_path()

    def run(self):
        run_cmds("sudo apt -y install pocketsphinx")
        self.generate_new_model()
        self.test_new_model()
        input("backup audio in /etc/audio then press enter")

    def generate_new_model(self):
        for func in [self.make_file_dirs,
                     self.record_files,
                     self.copy_files,
                     self.install_sphinx_base,
                     self.run_sphinx_fe,
                     self.download_proper_en,
                     self.convert_mdef,
                     self.download_sphinxtrain,
                     self.run_bw,
                     # self.run_mllr,
                     self.run_adapt]:
            logging.info(f"In {func.__name__}")
            func()

    def test_new_model(self):
        self.write_test_files()
        self.run_test_decoder()

    def make_file_dirs(self):
        delete_paths(self.tuned_path)
        makedirs(self.tuned_path)
        if not os.path.exists(self.audio_path):
            makedirs(self.audio_path)

    def record_files(self):
        phrase_fnames = list(self.phrase_iter())
        with open(self.audio_transcription_path, "a+") as transcription:
            with open(self.audio_file_ids_path, "a+") as f_ids:
                for i, (phrase, fname) in enumerate(phrase_fnames):
                    finished = self.record_phrase(phrase, fname)
                    f_ids.write(fname + "\n")
                    transcription.write(f"<s> {phrase} </s> ({fname})\n")
                    if finished:
                        break
                    print(f"{i + 1}/{len(phrase_fnames)} complete")
        input(f"check wave files in {self.audio_path}, then hit enter")

    def copy_files(self):
        run_cmds(f"cd {self.audio_path} && cp -R * {self.tuned_path}")
        # Using bash instead of python to closely follow directions on
        # https://cmusphinx.github.io/wiki/tutorialadapt/
        for _dir in ["en-us",
                     "cmudict-en-us.dict",
                     "en-us.lm.bin"]:
            path = os.path.join(self.model_path, _dir)
            run_cmds(f"cp -a {path} {self.tuned_path}")

    def install_sphinx_base(self):
        # https://bangladroid.wordpress.com/2017/02/16/installing-cmu-sphinx-on-ubuntu/
        run_cmds("sudo apt-get install -y gcc automake autoconf libtool "
                       "bison swig python-dev libpulse-dev")
        sphinx_path = os.path.join(self.tuned_path, "sphinx-src")
        makedirs(sphinx_path, remake=True)
        url = "https://github.com/cmusphinx/sphinxbase.git"
        # sudo is used on the first command to ensure it's use
        run_cmds([f"sudo ls ",
                        f"cd {sphinx_path}",
                        f"git clone {url}",
                        "cd sphinxbase",
                        "./autogen.sh",
                        f"make -j {cpu_count()}",
                        "sudo make install",
                        f"cp src/sphinx_fe/sphinx_fe {self.tuned_path}"],
                        stdout=True)

    def run_sphinx_fe(self):
        run_cmds([f"cd {self.tuned_path}",
                       (f"sphinx_fe -argfile en-us/feat.params "
                        f"-samprate 16000 -c {self.file_ids_path} "
                        "-di . -do . -ei wav -eo mfc -mswav yes")],
                       stdout=True)

    def download_proper_en(self):

        url = ("https://phoenixnap.dl.sourceforge.net/project/cmusphinx/"
               "Acoustic%20and%20Language%20Models/US%20English/"
               "cmusphinx-en-us-5.2.tar.gz")
        path = os.path.join(self.tuned_path, "larger_sphinx.tar.gz")
        logging.info("downloading file, this may take a while")
        download_file(url, path)
        logging.info("downloaded")
        with tarfile.open(path) as f:
            old_en_us_path = os.path.join(self.tuned_path, "en-us")
            delete_paths(old_en_us_path)
            def is_within_directory(directory, target):
                
                abs_directory = os.path.abspath(directory)
                abs_target = os.path.abspath(target)
            
                prefix = os.path.commonprefix([abs_directory, abs_target])
                
                return prefix == abs_directory
            
            def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
            
                for member in tar.getmembers():
                    member_path = os.path.join(path, member.name)
                    if not is_within_directory(path, member_path):
                        raise Exception("Attempted Path Traversal in Tar File")
            
                tar.extractall(path, members, numeric_owner=numeric_owner) 
                
            
            safe_extract(f, old_en_us_path)
            run_cmds([f"cd {old_en_us_path}",
                            f"mv * old_folder",
                            "cd old_folder",
                            "mv * ..",
                            "rm -rf old_folder"],
                            stdout=True)

    def convert_mdef(self):
        #run_cmds("sudo apt -y install pocketsphinx")
        run_cmds([f"cd {self.tuned_path}",
                        "git clone git@github.com:cmusphinx/pocketsphinx.git",
                        "cd pocketsphinx",
                        "./autogen.sh",
                        f"make -j {cpu_count()}",
                        "sudo make install"],
                        stdout=True)
        tool_path = os.path.join(self.tuned_path,
                                 "pocketsphinx",
                                 "src",
                                 "programs",
                                 "pocketsphinx_mdef_convert")
        path = os.path.join(self.tuned_path, "en-us/mdef")
        run_cmds(f"{tool_path} -text {path} {path}.txt",
                        stdout=True)

    def download_sphinxtrain(self):
        # Must get installed from source for fixes
        run_cmds([f"cd {self.tuned_path}",
                        "git clone git@github.com:cmusphinx/sphinxtrain.git",
                        "cd sphinxtrain",
                        "./autogen.sh",
                        f"make -j {cpu_count()}",
                        "sudo make install"],
                        stdout=True)
        for fname in ["bw", "map_adapt", "mk_s2sendump", "mllr_solve"]:
            old_path = os.path.join("/usr/local/libexec/sphinxtrain/", fname)
            new_path = os.path.join(self.tuned_path, fname)
            run_cmds(f"cp {old_path} {new_path}")
        
    def run_bw(self):
        run_cmds([f"cd {self.tuned_path}",
                        ("sudo ./bw \\\n"
                         " -hmmdir en-us \\\n"
                         " -moddeffn en-us/mdef.txt \\\n"
                         #"-ts2cbfn .ptm. \\\n"
                         " -ts2cbfn .cont. \\\n"
                         " -feat 1s_c_d_dd \\\n"
                         #"-svspec 0-12/13-25/26-38 \\\n"
                         " -lda en-us/feature_transform \\\n"
                         " -cmn current \\\n"
                         " -agc none \\\n"
                         " -dictfn cmudict-en-us.dict \\\n"
                         f" -ctlfn {self.file_ids_name} \\\n"
                         f" -lsnfn {self.transcription_name} \\\n"
                         " -accumdir .")], stdout=True)

    def run_adapt(self):
        cmds = [f"cd {self.tuned_path}",
                "cp -R en-us en-us-adapt",
                ("./map_adapt -moddeffn en-us/mdef.txt -ts2cbfn .cont. "
                 "-meanfn en-us/means -varfn en-us/variances -mixwfn "
                 "en-us/mixture_weights -tmatfn en-us/transition_matrices "
                 "-accumdir . -mapmeanfn en-us-adapt/means -mapvarfn "
                 "en-us-adapt/variances -mapmixwfn "
                 "en-us-adapt/mixture_weights -maptmatfn "
                 "en-us-adapt/transition_matrices")]
        run_cmds(cmds, stdout=True)

    def run_mllr(self):
        # NOTE: not nearly as effective as run_adapt.
        # Now we just use that instead
        run_cmds([f"cd {self.tuned_path}",
                  ("./mllr_solve\\\n"
                   " -meanfn en-us/means \\\n"
                   " -varfn en-us/variances \\\n"
                   " -outmllrfn mllr_matrix -accumdir .")],
                  stdout=True)

    def write_test_files(self):
        makedirs(self.test_dir)
        wav_dir = os.path.join(self.test_dir, "wav/")
        makedirs(wav_dir)
        old_lm = os.path.join(self.tuned_path, "en-us.lm.bin")
        new_lm = os.path.join(self.test_dir, "en-us.lm.bin")
        old_dict = os.path.join(self.tuned_path, "cmudict-en-us.dict")
        new_dict = os.path.join(self.test_dir, "cmudict-en-us.dict")
        old_hmm = os.path.join(self.tuned_path, "en-us")
        new_hmm = os.path.join(self.test_dir, "en-us")
        old_mllr_matrix = os.path.join(self.tuned_path, "mllr_matrix")
        new_mllr_matrix = os.path.join(self.test_dir, "mllr_matrix")
        run_cmds([f"cd {self.tuned_path}",
                  f"cp {self.file_ids_path} {self.test_file_ids_path}",
                  (f"cp {self.transcription_path} "
                   f"{self.test_transcription_path}"),
                   f"cp *wav {wav_dir}",
                   f"cp {old_lm} {new_lm}",
                   f"cp {old_dict} {new_dict}",
                   f"cp -R {old_hmm} {new_hmm}",
                   #f"cp {old_mllr_matrix} {new_mllr_matrix}",
                   f"cp {self.tuned_path}/sphinxtrain/scripts/decode/word_align.pl ./test/"],
                   stdout=True)

    def run_test_decoder(self):
        for adapt in [False, True]:
            if adapt:
                run_cmds([f"cd {self.tuned_path}",
                          f"rm -rf test/en-us",
                          f"cp -R en-us-adapt test/en-us"])
            tool_path = os.path.join(self.tuned_path,
                                     "pocketsphinx",
                                     "src",
                                     "programs",
                                     "pocketsphinx_batch")
            run_cmds((f"cd {self.test_dir} && \\\n"
                      f"{tool_path} \\\n"
                      f" -adcin yes \\\n"
                      f" -cepdir wav \\\n"
                      f" -cepext .wav \\\n"
                      f" -ctl test.fileids \\\n"
                      f" -lm en-us.lm.bin \\\n"
                      f" -dict cmudict-en-us.dict \\\n"
                      f" -hmm en-us \\\n"  # for example en-us
                      f" -hyp test.hyp"),
                            stdout=True)
            run_cmds([f"cd {self.test_dir}",
                      "perl word_align.pl test.transcription test.hyp"],
                      stdout=True)
            input(f"test complete with adapt as {adapt}, hit enter")


    def record_phrase(self, phrase, fname):
        satisfied = False
        while not satisfied:
            # spawn process that records audio
            with Pool(4, 0) as pool:
                input(f"Get ready to record, then hit enter: {phrase}")
                m = Manager()
                q = m.Queue()
                pool.apipe(self.audio_recording_process, fname, q)
                input()
                q.put("done")
            retry_key = "n"
            finished_key = "d"
            ans = input(f"Satisfied? enter {retry_key} to retry or {finished_key} to be done")
            if retry_key not in ans.lower():
                satisfied = True
        return finished_key in ans

    def audio_recording_process(self, fname, q):
        # TODO: refactor this to include this stuff as class attrs of wrapper
        stream, p, chunk_size = sr.Speech_Recognition_Wrapper.start_audio(self)
        write_to_stdout("Ready! Record, then hit enter!")
        frames = []
        while q.empty():
            frames.append(stream.read(chunk_size))
        frames.append(stream.read(chunk_size))
        stream.close()
        p.terminate()

        with wave.open(self.file_to_audio_path(fname) + ".wav", 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(16000)
            wf.writeframes(b''.join(frames))


    def phrase_iter(self):
        """Returns phrase and fnames"""

        f = []
        for (dirpath, dirnames, filenames) in os.walk(self.audio_path):
            f.extend(filenames)
            break

        tuning_phrases_set = set(self.tuning_phrases)
        previously_seen_phrases = []
        for fname in f:
            if self.username in fname:
                phrase = re.findall(".*\d_(.*).wav", fname)[0].replace("_", " ")
                if phrase in tuning_phrases_set:
                    previously_seen_phrases.append(phrase)
        prev_seen_phrases_set = set(previously_seen_phrases)

        new_words = [x for x in self.tuning_phrases
                     if x not in prev_seen_phrases_set or "tab" in x or "town" in x or "scroll" in x]
        if len(new_words) == 0:
            for i, phrase in enumerate(self.tuning_phrases):
                yield phrase, self.audio_fname(i, phrase)
        else:
            for i, phrase in enumerate(new_words):
                yield phrase, self.audio_fname(i, phrase)
            for j, phrase in enumerate(previously_seen_phrases):
                yield phrase, self.audio_fname(j + i, phrase)

    def file_to_audio_path(self, fname):
        return os.path.join(self.audio_path, fname)

    def audio_fname(self, num, phrase):
        return f"{self.session_id}{num:04}_{phrase.replace(' ', '_')}"

    @property
    def audio_transcription_path(self):
        return os.path.join(self.audio_path, self.transcription_name)

    @property
    def audio_file_ids_path(self):
        return os.path.join(self.audio_path, self.file_ids_name)



    @property
    def transcription_path(self):
        return os.path.join(self.tuned_path, self.transcription_name)

    @property
    def file_ids_path(self):
        return os.path.join(self.tuned_path, self.file_ids_name)

    @property
    def test_dir(self):
        return os.path.join(self.tuned_path, "test")

    @property
    def test_transcription_path(self):
        return os.path.join(self.test_dir, self.test_transcription_name)

    @property
    def test_file_ids_path(self):
        return os.path.join(self.test_dir, self.test_file_ids_name)
