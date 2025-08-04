from huggingface_hub import hf_hub_download
from dotenv import load_dotenv
import os

load_dotenv()

HF_TOKEN = os.getenv("HUGGING_FACE_TOKEN")

# download rmvpe.pt from the lj1995/VoiceConversionWebUI repo
hf_hub_download(
    repo_id="lj1995/VoiceConversionWebUI",
    filename="rmvpe.pt",
    local_dir="assets/rmvpe",
    token=HF_TOKEN
)
