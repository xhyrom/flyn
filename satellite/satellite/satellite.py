from enum import Enum, auto
from pathlib import Path

from .asr.asr import AutomaticSpeechRecognitionService
from .config import Config
from .core.client import CoreClient
from .debug import sneaky_throws
from .leds import initialize_lantern
from .microphone import MicrophoneInput
from .speaker import SpeakerOutput
from .tts.tts import TextToSpeechService
from .wake import WakeService


class State(Enum):
    OFF = auto()
    IDLE = auto()
    LISTENING = auto()
    THINKING = auto()
    SPEAKING = auto()


class Satellite:
    state: State
    config: Config

    microphone: MicrophoneInput
    speaker: SpeakerOutput

    wake_service: WakeService
    asr_service: AutomaticSpeechRecognitionService
    tts_service: TextToSpeechService
    core_client: CoreClient

    def __init__(self, config: Config) -> None:
        self.state = State.OFF
        self.config = config

        self.lantern = initialize_lantern(config.led)

        self.microphone = MicrophoneInput()
        self.speaker = SpeakerOutput()

        self.wake_service = WakeService(
            [Path(p) for p in config.wake.model_paths],
            config.wake.threshold,
        )
        self.asr_service = config.asr.create_service()
        self.tts_service = config.tts.create_service()
        self.core_client = CoreClient(config.core.url, config.core.api_key)

    @sneaky_throws
    async def run(self) -> None:
        self.state = State.IDLE
        self.lantern.always_on()

        while True:
            if not self.wake_service.run(self.microphone):
                pass

            self.lantern.wakeup()

            self.state = State.LISTENING

            print("Listening...")
            transcription = self.asr_service.run(self.microphone)
            self.lantern.listen()

            print("Heard:", transcription)

            self.state = State.THINKING
            self.lantern.think()

            response = await self.core_client.ask(transcription)

            if "error" in response:
                print(f"Error from Core API: {response['error']}")
                response_text = (
                    "Sorry, I'm having trouble connecting to my brain right now."
                )
            else:
                print(f"Core response: {response}")
                response_text = response.get(
                    "response", "I'm not sure how to respond to that."
                )

            self.state = State.SPEAKING
            self.lantern.speak()

            for audio in self.tts_service.synthesize(response_text):
                self.speaker.play_audio(audio)

            self.state = State.IDLE
            self.lantern.always_on()
