from django.shortcuts import render
from django.contrib.auth import logout
from django.utils import timezone

class SaasSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Se o usuário está logado e NÃO é o superadmin (você)
        if request.user.is_authenticated and not request.user.is_superuser:
            empresa = request.user.empresa
            
            # 1. Checa se a empresa existe
            if not empresa:
                logout(request)
                return render(request, 'core/bloqueado.html', {'motivo': 'sem_empresa'})

            # 2. Checa se está bloqueada manualmente
            if not empresa.ativa:
                logout(request)
                return render(request, 'core/bloqueado.html', {'motivo': 'bloqueada'})
            
            # 3. Checa se venceu a assinatura
            if empresa.data_vencimento and empresa.data_vencimento < timezone.now().date():
                # Opcional: logout(request) se quiser ser rígido
                # Ou apenas avisa:
                request.aviso_vencimento = True 

        response = self.get_response(request)
        return response