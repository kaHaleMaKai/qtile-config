import traceback as _traceback


_ignored_module_keys = set([
  "__builtins__",
  "__cached__",
  "__doc__",
  "__file__",
  "__loader__",
  "__name__",
  "__package__",
  "__spec__",
  "_os",
  "_importlib_util",
])


try:
    import custom_config as config
    import time
    time.sleep(0.5)
    print("config loaded")
except Exception as e:  #NOQA
    print(_traceback.format_exc())
    print("falling back to default config")
    import default_config as config

print("putting config into global namespace")
for key in dir(config):
    if key in _ignored_module_keys:
        continue
    print("  * ", key)
    globals()[key] = getattr(config, key)

print("initialization done")
