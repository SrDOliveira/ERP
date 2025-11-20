#!/usr/bin/env bash
# Sair se der erro
set -o errexit

# 1. Instalar dependências
pip install -r requirements.txt

# 2. Coletar arquivos estáticos (CSS/JS)
python manage.py collectstatic --no-input

# 3. Rodar as migrações no banco de dados
python manage.py migrate