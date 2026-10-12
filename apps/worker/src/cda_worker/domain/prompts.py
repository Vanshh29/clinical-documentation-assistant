import os
from pathlib import Path

from cda_worker.domain.ports import Message, Prompt

# Installed images have no repo-relative prompts folder: set CDA_PROMPTS_DIR there.
DEFAULT_DIR = Path(
    os.environ.get("CDA_PROMPTS_DIR") or Path(__file__).resolve().parents[3] / "prompts"
)


class PromptBuilder:
    """Loads versioned prompt files. Prompts are never inline strings (see prompts/<version>/)."""

    def __init__(self, version: str = "v1", base_dir: Path = DEFAULT_DIR) -> None:
        folder = base_dir / version
        self.version = version
        self._system = (folder / "system.md").read_text(encoding="utf-8")
        self._user = (folder / "user.md").read_text(encoding="utf-8")

    def build(self, note_text: str, feedback: list[str] | None = None) -> Prompt:
        user = Message("user", self._user.replace("{note}", note_text))
        messages = [user]
        if feedback:
            messages.append(
                Message(
                    "user",
                    "Your previous answer was rejected for these reasons:\n"
                    + "\n".join(f"- {line}" for line in feedback[:20])
                    + "\nReturn a corrected JSON object. Quote the note verbatim; use null "
                    "for anything the note does not document.",
                )
            )
        return Prompt(system=self._system, messages=messages, version=self.version)
