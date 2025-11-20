from django.contrib import admin
from django.urls import path, include
from django.conf import settings               # <--- IMPORTANTE
from django.conf.urls.static import static     # <--- IMPORTANTE

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),    # <--- Esta linha conecta o arquivo do Passo 2
]

# --- ADICIONE ESTE BLOCO NO FINAL DO ARQUIVO ---
# Isso diz ao Django: "Se estiver em modo DEBUG, mostre as fotos que estão na pasta MEDIA"
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)