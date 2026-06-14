import argparse
import os
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import types

def main():
    parser = argparse.ArgumentParser(description="Generate audio using Gemini Text-to-Speech")
    parser.add_argument("--text", type=str, required=True, help="The text to convert to speech.")
    parser.add_argument("--voice", type=str, default="Aoede", help="The prebuilt voice name (default: Aoede). Available: Kore, Puck, Aoede, Fenrir, Zephyr.")
    parser.add_argument("--output", type=str, default="output.wav", help="The path to save the output file (default: output.wav).")
    parser.add_argument("--style", type=str, help="Instructions for tone/emotion (e.g., 'cheerful', 'whispering', 'excited').")

    args = parser.parse_args()

    # Load environment variables from .env if present
    load_dotenv()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment or .env file.")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    # Format the prompt
    prompt = args.text
    if args.style:
        prompt = f"Say {args.style}: {args.text}"

    # Setup the voice config
    speech_config = types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name=args.voice
            )
        )
    )

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-tts-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=speech_config
            )
        )

        # Write to output file
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            # Depending on how the SDK returns the audio
            # Sometimes it's inline_data, sometimes another structure
            audio_part = None
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    audio_part = part.inline_data
                    break

            if audio_part and audio_part.data:
                with open(args.output, "wb") as f:
                    f.write(audio_part.data)
                print(f"Successfully generated audio and saved to {args.output}")
            else:
                print("Error: Response did not contain audio data.")
                print("Response:", response)
                sys.exit(1)
        else:
            print("Error: No valid content in response.")
            sys.exit(1)

    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
