from datetime import datetime
import itertools
import logging
import os
import re
import sys
from time import perf_counter

import pyaudio

from .audio_tuner import Audio_Tuner
from .defaults import default_keywords_dict

from pocketsphinx import DefaultConfig, Decoder, get_model_path, get_data_path


class Speech_Recognition_Wrapper:

    keywords_path = "/tmp/kws.list"
    dict_path = "/tmp/en.dict"

    def __init__(self,
                 keywords_dict=None,
                 redownload=True,
                 callback_dict={},
                 removed_words=[],
                 tuning_phrases=[],
                 test=False):
        """Saves and if redownload then writes keywords"""

        # model path for pocket sphinx
        self.model_path = get_model_path()
        # Sets default keywords dict
        if keywords_dict is None:
            keywords_dict = default_keywords_dict
        self.keywords_dict = keywords_dict

        if redownload:
            self.write_keywords()
            self.write_language_dict(removed_words)

        self.config = self.get_config()

        # strings for keys, functions are the values
        self.callbacks_dict = callback_dict
        if len(tuning_phrases) > 0:
            Audio_Tuner(tuning_phrases, test=test).run()

    def write_keywords(self):
        """Writes keywords to their own file"""

        with open(self.keywords_path, "w") as f:
            for keyword, multiplier in self.keywords_dict.items():
                f.write(f"{keyword} /1e{multiplier}/\n")

    def write_language_dict(self, words_to_remove):
        """Writes the language dictionary of the keywords"""

        logging.debug("Writing new dict")
        with open(os.path.join(self.model_path,
                               'cmudict-en-us.dict'), "r") as f:
            lines = list(f.readlines())

        words_to_remove = set(words_to_remove)

        lines_to_keep = []

        for line in lines:
            first_word = line.split()[0]
            # Sometimes fmt blackboard(2) <pronounciation>
            if "(" in first_word:
                first_word = first_word.split("(")[0]
            if first_word not in words_to_remove:
                lines_to_keep.append(line)

        with open(self.dict_path, "w") as f:
           for line in lines_to_keep:
               f.write(line)
        return


        """
        all_words = []
        for keyword in self.keywords_dict:
            all_words.extend(keyword.split())
        all_words = set(all_words)

        word_dict = {}
        for word in sorted(all_words):
            word_dict[word] = []

        for line in lines:
            first_word = line.split(" ")[0]
            if "(" in first_word:
                first_word = first_word.split("(")[0]
            if first_word in all_words:
                pronounciation = " ".join(line.split()[1:]).replace("\n", "")
                word_dict[first_word].append(pronounciation)

        with open(self.dict_path, "w") as f:
            for keyword in self.keywords_dict:
                pronounciations = []
                for word in keyword.split():
                    pronounciations.append(word_dict[word])
                for i, combo in enumerate(list(itertools.product(*pronounciations))):
                    line = "-".join(keyword.split())
                    if i + 1 > 1:
                        line += f"({i + 1})"
                    line += " " + " ".join(combo) + "\n"
                    f.write(line)



        return
        """
        save_lines = []

        all_words = []
        for keyword in self.keywords_dict:
            all_words.extend(keyword.split())
        all_words = set(all_words)

        for line in lines:
            first_word = line.split(" ")[0]
            if first_word in all_words or first_word.split("(")[0] in all_words:
                save_lines.append(line)

        with open(self.dict_path, "w") as f:
            for line in save_lines:
                f.write(line)

    def get_config(self):
        # Create a decoder with a certain model
        config = DefaultConfig()
        config.set_string('-hmm', os.path.join(self.model_path, 'en-us'))
        config.set_string('-lm', os.path.join(self.model_path, 'en-us.lm.bin'))

        # To do this, just only copy the words you want over to another file
        config.set_string('-dict', self.dict_path)
        #config.set_string('-dict', os.path.join(self.model_path,
        #                                        'cmudict-en-us.dict'))
        config.set_string('-kws', self.keywords_path)
        config.set_string("-logfn", '/dev/null')
        config.set_boolean("-verbose", False)

        return config

    def run(self):
        stream, _, __ = self.start_audio()
        self.run_decoder(stream)

    def start_audio(self):
        # https://github.com/spatialaudio/python-sounddevice/
        # issues/11#issuecomment-155836787
        devnull = os.open(os.devnull, os.O_WRONLY)
        old_stderr = os.dup(2)
        sys.stderr.flush()
        os.dup2(devnull, 2)
        os.close(devnull)
        chunks = 1024
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=16000,
                        input=True,
                        frames_per_buffer=chunks)
        stream.start_stream()
        return stream, p, chunks
        os.dup2(old_stderr, 2)
        os.close(old_stderr)

    def run_decoder(self, stream):
        # Process audio chunk by chunk. On keyword detected process/restart
        decoder = Decoder(self.config)
        decoder.start_utt()

        last_decode_str = None
        last_decode_time = perf_counter()
        # https://stackoverflow.com/a/47371315/8903959
        while True:
            buf = stream.read(1024)
            if buf:
                decoder.process_raw(buf, False, False)
            else:
                break
            if decoder.hyp() is not None:
                if last_decode_str == decoder.hyp().hypstr:
                    reset_max = 5
                    if perf_counter() - last_decode_time > reset_max:
                        print(f"No kwrds in the last {reset_max}s, resetting\r")
                        decoder.end_utt()
                        decoder.start_utt()
                    continue
                
                else:
                    last_decode_str = decoder.hyp().hypstr
                    last_decode_time = perf_counter()
                    print(decoder.hyp().hypstr + "\r")

                
                just_restarted = False
                for keyword, callback in self.callbacks_dict.items():
                    if len(re.findall(r"\b(" + f"{keyword}).*",
                                      decoder.hyp().hypstr)) > 0:
                        print([(seg.word, seg.prob) for seg in decoder.seg()])
                        print(f"\nDetected keyword, running {callback.__name__}")
                        decoder.end_utt()
                        callback(decoder.hyp().hypstr)
                        print("Listening again\r")

                        decoder.start_utt()
                        just_restarted = True
                        break
                
                if not just_restarted and len(decoder.hyp().hypstr) > 25:
                    print("No keyword, restarting search\r")
                    decoder.end_utt()
                    decoder.start_utt() 
