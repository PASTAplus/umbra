# -*- coding: utf-8 -*-

""":Mod: __init__

:Synopsis:

:Author:
    ide

:Created:
    6/23/21
"""
import logging
import os

import daiquiri
from flask import Flask, session
from flask_bootstrap import Bootstrap

from config import Config

cwd = os.path.dirname(os.path.realpath(__file__))
logfile = Config.LOG_FILE
daiquiri.setup(level=logging.INFO,
               outputs=(daiquiri.output.File(logfile,
                                             formatter=daiquiri.formatter.ColorFormatter(
                                                fmt="%(asctime)s [PID %(process)d] [%(levelname)s] "
                                                        "%(name)s -> %(message)s")), 'stdout',
                        ))
logger = daiquiri.getLogger(__name__)

app = Flask(__name__)
bootstrap = Bootstrap(app)

# Importing these modules causes the routes and error handlers to be associated
# with the blueprint. It is important to note that the modules are imported at
# the bottom of the webapp/__init__.py script to avoid errors due to circular
# dependencies.

from webapp.creators.creators import creators_bp
app.register_blueprint(creators_bp, url_prefix='/creators')
