# voice-gpt

This project is a Discord voice chat bot that is powered by ChatGPT and Whisper. It allows users to have "natural" conversations with the bot in a voice chat channel.

## Requirements

- Python 3.9?
- Discord account
- OpenAI API key

## Installation

1. Clone the repository:

```bash
git clone https://github.com/edde746/voice-gpt.git
cd voice-gpt
```

2. Install the dependencies:

```bash
pip install -r requirements.txt
```

3. Create a Discord bot and add it to your server. You can follow this [guide](https://discordpy.readthedocs.io/en/latest/discord.html) to do so.


4. Copy the `config.example.py` file to `config.py` and fill in the required information.

5. Run the bot:

```bash
python main.py
```

## Usage

Once the bot is running, you can use the `/join` slash command to have the bot join your voice channel. You can then use the `/leave` slash command to have the bot leave the voice channel.

It has quite a big delay when responding, it's not a great experience but it's still fun to play around with.