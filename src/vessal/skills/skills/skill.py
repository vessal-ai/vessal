"""skills — UI-only Skill exposing a management view for installed Skills."""


class Skills:
    name = "skills"
    summary = "Inventory and management UI for installed Skills."
    guide = None
    tools: list[str] = []

    def __init__(self, data_dir=None):
        self._data_dir = data_dir
