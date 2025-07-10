# services/web-app/app/utils/extensions.py

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flasgger import Swagger

# 建立擴充套件的實例，但尚未與 app 綁定
# 綁定操作將在 Application Factory (create_app) 中完成
db = SQLAlchemy()
migrate = Migrate()
swagger = Swagger()
