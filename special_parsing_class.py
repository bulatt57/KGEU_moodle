class DualKeyDict:
    def __init__(self):
        self._store = {}

    def fromkeys(self, keys, value):
        for key in keys:
            self._store[key] = value

    def __setitem__(self, keys, value):
        if isinstance(keys, tuple):
            self._store[keys] = value
        else:
            self._store[(keys,)] = value

    def __getitem__(self, keys):
        if isinstance(keys, tuple):
            return self._store[keys]
        else:
            return self._store[(keys,)]

    def __repr__(self):
        return str(self._store)

    def format_items(self):
        formatted_strings = []
        for keys, value in self._store.items():
            keys_str = ". ".join(keys)
            formatted_strings.append(f"{keys_str}")
        return "\n".join(formatted_strings)

    def get_keys(self):
        keys_list = [".".join(keys) for keys in self._store.keys()]
        return "\n".join(keys_list)

    def __len__(self):
        return len(self._store)
