from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.utils import timezone
from django.urls import reverse

class SaasSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Lista de URLs que NÃO devem ser bloqueadas (segurança para não travar o sistema)
        # /admin/ -> Para você conseguir entrar e desbloquear
        # /logout/ -> Para o cliente conseguir sair da conta bloqueada
        # /static/ e /media/ -> Para o CSS e as imagens carregarem na tela de bloqueio
        urls_liberadas = [
        '/admin/', '/logout/', '/login/', '/cadastro/', # <--- Adicione Login e Cadastro   
        '/static/', '/media/', '/webhook/' # <--- Adicione Webhook também para o Asaas conseguir avisar         '/static/', '/media/'
        ]
        
        # Se o usuário não está logado ou é o dono do sistema (Você), deixa passar livre
        if not request.user.is_authenticated or request.user.is_superuser:
            return self.get_response(request)

        # Se a página que ele quer acessar está na lista liberada, deixa passar
        for path in urls_liberadas:
            if request.path.startswith(path):
                return self.get_response(request)

        # --- AQUI COMEÇA A SEGURANÇA ---
        if hasattr(request.user, 'empresa') and request.user.empresa:
            empresa = request.user.empresa
            hoje = timezone.now().date()
            
            # 1. Checa se a empresa foi travada manualmente por você (Inadimplência grave)
            if not empresa.ativa:
                logout(request)
                return render(request, 'core/bloqueado.html', {'motivo': 'bloqueada'})

            # 2. Checa se venceu o Teste Grátis ou a Mensalidade
            if empresa.data_vencimento and empresa.data_vencimento < hoje:
                # Em vez de só avisar, agora nós mostramos a tela de cobrança e impedimos o acesso
                return render(request, 'core/planos.html', {'empresa': empresa})

        return self.get_response(request)
    
        return response