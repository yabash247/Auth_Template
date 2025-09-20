from .base import *
import os, environ
environ.Env.read_env(os.path.join(BASE_DIR, "env", ".env.dev"))

