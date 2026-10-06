# Settings identity inputs

**Planned** verification fix discovered during signed feature testing. Table test
failed_config_merge_retries_same_settings_object intermittently skips changed config.
Both credit stores cache only id(settings); temporary objects can be collected and ID reused.
Existing singleton production settings normally mask this; reload/test sessions expose it.
