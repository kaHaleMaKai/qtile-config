from pathlib import Path
from libqtile import confreader

# cur_dir = Path(__file__).absolute().parent
cur_dir = Path.cwd().absolute()

config_file = cur_dir / "config.py"
c = confreader.Config(str(config_file))

c.load()
c.validate()


c = confreader.Config(str(config_file))
c.load()
c.validate()
