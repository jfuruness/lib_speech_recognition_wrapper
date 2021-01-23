from datetime import datetime
import os
import re
from time import perf_counter

import pyaudio

from .defaults import default_keywords_dict

from pocketsphinx import DefaultConfig, Decoder, get_model_path, get_data_path


class Speech_Recognition_Wrapper:

    keywords_path = "/tmp/kws.list"
    dict_path = "/tmp/en.dict"

    def __init__(self,
                 keywords_dict=None,
                 redownload=True,
                 callback_dict={}):
        """Saves and if redownload then writes keywords"""

        # model path for pocket sphinx
        self.model_path = get_model_path()

        # Sets default keywords dict
        if keywords_dict is None:
            keywords_dict = default_keywords_dict
        self.keywords_dict = keywords_dict

        if redownload:
            self.write_keywords()
            self.write_language_dict()

        self.config = self.get_config()

        # strings for keys, functions are the values
        self.callback_dict = callback_dict

    def write_keywords(self):
        """Writes keywords to their own file"""

        with open(self.keywords_path, "w") as f:
            for keyword, multiplier in keywords.items():
                f.write(f"{keyword} /1e-{multiplier}/\n")

    def write_language_dict(self):
        """Writes the language dictionary of the keywords"""

        with open(os.path.join(self.model_path,
                               'cmudict-en-us.dict'), "r") as f:
            lines = f.readlines()

        save_lines = []
        for keyword in self.keywords_dict:
            for word in keyword.split():
                for line in lines:
                    # fix later
                    if len(re.findall(r"^{keyword}(:?\(\d\))*.*", line)) > 0:
                        save_lines.append(line)
                    if len(re.findall(r"^{keyword} .*", line)) > 0:
                        save_lines.append(line)

        input(save_lines)
        with open(self.dict_path, "w") as f:
            for line in save_lines:
                f.write(line + "\n")

    def get_config(self):
        # Create a decoder with a certain model
        config = DefaultConfig()
        config.set_string('-hmm', os.path.join(model_path, 'en-us'))
        config.set_string('-lm', os.path.join(model_path, 'en-us.lm.bin'))

        # To do this, just only copy the words you want over to another file
        config.set_string('-dict', self.dict_path)
        config.set_string('-kws', self.keywords_path)
        config.set_string("-logfn", '/dev/null')
        config.set_boolean("-verbose", False)

        return config

    def run(self):
        stream = self.start_audio()
        self.run_decoder(stream)

    def start_audio(self):
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=16000,
                        input=True,
                        frames_per_buffer=1024)
        stream.start_stream()

    def run_recorder(self):
        # Process audio chunk by chunk. On keyword detected process/restart
        decoder = Decoder(config)
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
                        print(f"No kwrds in the last {reset_max}s, resetting")
                        decoder.end_utt()
                        decoder.start_utt()
                    continue
                else:
                    last_decode_str = decoder.hyp().hypstr
                    last_decode_time = perf_counter()
                    print(decoder.hyp().hypstr)
                just_restarted = False
                for keyword, callback in self.callbacks_dict.items():
                    if len(re.findall(r"\b(" + f"{keyword}).*",
                                      decoder.hyp().hypstr)) > 0:
                        #print([(seg.word, seg.prob, seg.start_frame,
                        #seg.end_frame) for seg in decoder.seg()])
                        print(f"Detected keyword, running {callback.__name__}")
                        callback()
                        print("Listening again")
                        decoder.end_utt()
                        decoder.start_utt()
                        just_restarted = True
                        break
                if not just_restarted and len(decoder.hyp().hypstr) > 15:
                    print("No keyword, restarting search")
                    decoder.end_utt()
            decoder.start_utt()
