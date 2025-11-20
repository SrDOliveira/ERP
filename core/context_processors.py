from .models import Produto
from django.db.models import F

def notificacoes_estoque(request):
    if request.user.is_authenticated and hasattr(request.user, 'empresa') and request.user.empresa:
        count = Produto.objects.filter(
            empresa=request.user.empresa, 
            estoque_atual__lte=F('estoque_minimo')
        ).count()
        return {'notificacao_estoque_baixo': count}
    return {}