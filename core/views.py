# core/views.py

# --- 1. IMPORTS ---
import os
import uuid
import requests
import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count, F, Avg, Q, ExpressionWrapper, FloatField
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from weasyprint import HTML

# --- MODELOS E FORMS ---
from .models import (
    Venda, ItemVenda, Produto, Cliente, Lancamento, Empresa, 
    MovimentoCaixa, Caixa, FormaPagamento, Usuario,
    Categoria, Fornecedor
)
from .forms import (
    ProdutoForm, AberturaCaixaForm, FechamentoCaixaForm,
    CategoriaForm, FornecedorForm, ClienteForm, 
    ConfiguracaoEmpresaForm, UsuarioForm,
    CadastroLojaForm
)

# --- CONFIGURAÇÕES ASAAS ---
ASAAS_API_KEY = os.environ.get('ASAAS_API_KEY', '')
ASAAS_URL = os.environ.get('ASAAS_URL', 'https://www.asaas.com/api/v3')

# =========================================================
#  DASHBOARD
# =========================================================
@login_required
def dashboard(request):
    empresa_usuario = request.user.empresa
    hoje = timezone.now().date()
    
    # Estoque Baixo
    estoque_baixo_count = Produto.objects.filter(
        empresa=empresa_usuario, 
        estoque_atual__lte=F('estoque_minimo')
    ).count()

    # KPIs Financeiros
    vendas_hoje = Venda.objects.filter(empresa=empresa_usuario, data_venda__date=hoje, status='FECHADA')
    total_hoje = vendas_hoje.aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    qtd_vendas = vendas_hoje.count()
    
    # Gráfico
    sete_dias_atras = hoje - timedelta(days=7)
    ultimas_vendas = Venda.objects.filter(empresa=empresa_usuario).order_by('-data_venda')[:5]
    
    datas_grafico = []
    valores_grafico = []
    for i in range(6, -1, -1):
        d = hoje - timedelta(days=i)
        val = Venda.objects.filter(empresa=empresa_usuario, status='FECHADA', data_venda__date=d).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
        datas_grafico.append(d.strftime('%d/%m'))
        valores_grafico.append(float(val))

    return render(request, 'core/index.html', {
        'total_clientes': Cliente.objects.filter(empresa=empresa_usuario).count(),
        'total_produtos': Produto.objects.filter(empresa=empresa_usuario).count(),
        'estoque_baixo_count': estoque_baixo_count,
        'vendas_hoje': qtd_vendas,
        'total_hoje': total_hoje,
        'ultimas_vendas': ultimas_vendas,
        'datas_grafico': datas_grafico,
        'valores_grafico': valores_grafico,
    })

# =========================================================
#  AUTO-CADASTRO (SIGN UP)
# =========================================================
def cadastro_loja(request):
    if request.method == 'POST':
        form = CadastroLojaForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            
            # Cria CNPJ Provisório
            cnpj_provisorio = f"TEMP-{uuid.uuid4().hex[:8]}"

            # 1. Criar Empresa
            nova_empresa = Empresa.objects.create(
                nome_fantasia=data['nome_loja'],
                cnpj=cnpj_provisorio,
                ativa=True,
                data_vencimento=timezone.now().date() + timedelta(days=7), # 7 dias grátis
                plano='ESSENCIAL'
            )
            
            # 2. Criar Usuário Gerente
            novo_usuario = Usuario.objects.create_user(
                username=data['username'],
                email=data['email'],
                password=data['senha'],
                first_name=data['nome_usuario'],
                empresa=nova_empresa,
                cargo='GERENTE'
            )
            
            # 3. Onboarding (Dados Iniciais)
            Caixa.objects.create(empresa=nova_empresa, nome="Caixa Principal", observacao="Caixa padrão")
            FormaPagamento.objects.create(empresa=nova_empresa, nome="Dinheiro", taxa=0)
            FormaPagamento.objects.create(empresa=nova_empresa, nome="Cartão Crédito", taxa=3.5, dias_para_receber=30)
            FormaPagamento.objects.create(empresa=nova_empresa, nome="PIX", taxa=0)
            
            # 4. Logar e Redirecionar para Planos
            login(request, novo_usuario)
            messages.success(request, f"Bem-vindo! Sua loja foi criada. Escolha como deseja continuar.")
            return redirect('escolher_plano')
            
    else:
        form = CadastroLojaForm()
        
    return render(request, 'core/signup.html', {'form': form})

@login_required
def escolher_plano(request):
    return render(request, 'core/planos.html')

# =========================================================
#  PAGAMENTOS E ASSINATURA (ASAAS)
# =========================================================
@login_required
def iniciar_pagamento(request, plano):
    empresa = request.user.empresa
    
    # Verificação de CNPJ Real
    if "TEMP-" in empresa.cnpj or len(empresa.cnpj) < 11:
        messages.warning(request, "⚠️ Para emitir a cobrança, precisamos do seu CPF ou CNPJ real. Por favor, atualize abaixo.")
        return redirect('/configuracoes/?next=planos')

    # Define Valor
    if plano == 'ESSENCIAL': valor = 129.00
    elif plano == 'PRO': valor = 249.00
    else: return redirect('dashboard')

    # Verifica Chave API
    if not ASAAS_API_KEY:
        messages.error(request, "Erro: Chave API do Asaas não configurada no sistema.")
        return redirect('dashboard')

    headers = {"Content-Type": "application/json", "access_token": ASAAS_API_KEY}

    # Criar Cliente no Asaas
    if not empresa.asaas_customer_id:
        payload_cliente = {
            "name": empresa.nome_fantasia,
            "cpfCnpj": empresa.cnpj,
            "email": request.user.email,
        }
        try:
            response = requests.post(f"{ASAAS_URL}/customers", json=payload_cliente, headers=headers)
            if response.status_code == 200:
                empresa.asaas_customer_id = response.json()['id']
                empresa.save()
            else:
                erro_msg = response.json().get('errors', [{'description': 'Erro desconhecido'}])[0]['description']
                messages.error(request, f"Asaas recusou o cliente: {erro_msg}")
                return redirect('dashboard')
        except Exception as e:
            messages.error(request, f"Erro de conexão: {str(e)}")
            return redirect('dashboard')

    # Criar Cobrança
    payload_assinatura = {
        "customer": empresa.asaas_customer_id,
        "billingType": "UNDEFINED", 
        "value": valor,
        "nextDueDate": timezone.now().strftime('%Y-%m-%d'),
        "cycle": "MONTHLY",
        "description": f"Assinatura Nexum ERP - Plano {plano}"
    }

    try:
        response = requests.post(f"{ASAAS_URL}/subscriptions", json=payload_assinatura, headers=headers)
        if response.status_code == 200:
            return redirect(response.json()['billUrl'])
        else:
            messages.error(request, "Erro ao gerar cobrança no Asaas.")
            return redirect('dashboard')
    except Exception as e:
        messages.error(request, f"Erro técnico: {str(e)}")
        return redirect('dashboard')

@csrf_exempt 
def webhook_asaas(request):
    if request.method == 'POST':
        try:
            dados = json.loads(request.body)
            evento = dados.get('event')
            payment = dados.get('payment')
            
            if evento in ['PAYMENT_RECEIVED', 'PAYMENT_CONFIRMED']:
                customer_id = payment.get('customer')
                try:
                    empresa = Empresa.objects.get(asaas_customer_id=customer_id)
                    empresa.ativa = True
                    empresa.data_vencimento = timezone.now().date() + timedelta(days=30)
                    
                    valor_pago = float(payment.get('value', 0))
                    if valor_pago >= 249: empresa.plano = 'PRO'
                    else: empresa.plano = 'ESSENCIAL'
                        
                    empresa.save()
                    return JsonResponse({'status': 'recebido e liberado'})
                except Empresa.DoesNotExist:
                    return JsonResponse({'status': 'empresa nao encontrada'}, status=404)
            
            return JsonResponse({'status': 'ignorado'})
        except Exception as e:
            return JsonResponse({'status': 'erro', 'msg': str(e)}, status=500)
    return HttpResponseForbidden()

# =========================================================
#  CONTROLE DE CAIXA
# =========================================================
@login_required
def gerenciar_caixa(request):
    caixa_aberto = MovimentoCaixa.objects.filter(operador=request.user, status='ABERTO').first()
    if caixa_aberto:
        return render(request, 'core/caixa_aberto.html', {'movimento': caixa_aberto})
    return redirect('abrir_caixa')

@login_required
def abrir_caixa(request):
    if MovimentoCaixa.objects.filter(operador=request.user, status='ABERTO').exists():
        return redirect('gerenciar_caixa')

    if request.method == 'POST':
        form = AberturaCaixaForm(request.user, request.POST)
        if form.is_valid():
            movimento = form.save(commit=False)
            movimento.empresa = request.user.empresa
            movimento.operador = request.user
            movimento.save()
            return redirect('criar_venda') # Vai direto vender
    else:
        form = AberturaCaixaForm(request.user)
    
    return render(request, 'core/form_abrir_caixa.html', {'form': form})

@login_required
def fechar_caixa(request, movimento_id):
    movimento = get_object_or_404(MovimentoCaixa, id=movimento_id, operador=request.user, status='ABERTO')
    total_vendido = movimento.vendas.filter(status='FECHADA').aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    valor_esperado = movimento.valor_abertura + total_vendido

    if request.method == 'POST':
        form = FechamentoCaixaForm(request.user, request.POST, instance=movimento)
        if form.is_valid():
            movimento = form.save(commit=False)
            movimento.status = 'FECHADO'
            movimento.data_fechamento = timezone.now()
            movimento.diferenca = movimento.valor_fechamento - valor_esperado
            movimento.save()
            return redirect('dashboard')
    else:
        form = FechamentoCaixaForm(request.user, instance=movimento)

    return render(request, 'core/form_fechar_caixa.html', {
        'form': form, 
        'movimento': movimento,
        'total_vendido': total_vendido,
        'valor_esperado': valor_esperado
    })

# =========================================================
#  PDV E VENDAS
# =========================================================
@login_required
def criar_venda(request):
    caixa_aberto = MovimentoCaixa.objects.filter(operador=request.user, status='ABERTO').first()
    if not caixa_aberto:
        return render(request, 'core/erro_caixa_fechado.html')

    empresa = request.user.empresa
    cliente_padrao = Cliente.objects.filter(empresa=empresa).first()
    
    venda = Venda.objects.create(
        empresa=empresa,
        vendedor=request.user,
        cliente=cliente_padrao,
        status='ORCAMENTO',
        movimento_caixa=caixa_aberto
    )
    return redirect('pdv', venda_id=venda.id)

@login_required
def pdv(request, venda_id):
    venda = get_object_or_404(Venda, id=venda_id, empresa=request.user.empresa)
    
    if request.method == 'POST':
        acao = request.POST.get('acao')
        
        if request.POST.get('cliente'):
            venda.cliente_id = request.POST.get('cliente')
            venda.save()
            
        if acao == 'fechar_venda':
            forma_pagto_id = request.POST.get('forma_pagamento')
            
            if forma_pagto_id:
                total = sum(item.subtotal for item in venda.itens.all())
                venda.valor_total = total
                venda.status = 'FECHADA'
                venda.forma_pagamento_id = forma_pagto_id
                venda.save()
                
                if venda.cliente:
                    venda.cliente.data_ultima_compra = timezone.now()
                    venda.cliente.save()
                
                for item in venda.itens.all():
                    p = item.produto
                    p.estoque_atual -= item.quantidade
                    p.save()

                quer_nota = request.POST.get('emitir_fiscal')
                if quer_nota:
                    # Aqui entra API fiscal
                    venda.nota_fiscal_emitida = True
                    venda.save()
                    messages.success(request, "Venda Fechada! Nota Fiscal em processamento.")
                else:
                    messages.success(request, "Venda Fechada com sucesso.")

                Lancamento.objects.create(
                    empresa=venda.empresa,
                    tipo='RECEITA',
                    titulo=f"Venda #{venda.id} - {venda.forma_pagamento.nome}",
                    valor=total,
                    data_vencimento=timezone.now().date(),
                    data_pagamento=timezone.now().date(),
                    pago=True,
                    venda_origem=venda
                )
                return redirect('dashboard')

    produtos = Produto.objects.filter(empresa=request.user.empresa, ativo=True)
    clientes = Cliente.objects.filter(empresa=request.user.empresa)
    formas_pagamento = FormaPagamento.objects.filter(empresa=request.user.empresa)
    total = sum(item.subtotal for item in venda.itens.all())
    
    return render(request, 'core/pdv.html', {
        'venda': venda,
        'produtos': produtos,
        'clientes': clientes,
        'formas_pagamento': formas_pagamento,
        'total': total
    })

@login_required
@require_POST
def adicionar_item(request, venda_id):
    venda = get_object_or_404(Venda, id=venda_id)
    produto_id = request.POST.get('produto')
    quantidade = int(request.POST.get('quantidade', 1))
    
    if produto_id:
        produto = get_object_or_404(Produto, id=produto_id)
        ItemVenda.objects.create(
            venda=venda, produto=produto, quantidade=quantidade, 
            preco_unitario=produto.preco_venda
        )
    return redirect('pdv', venda_id=venda.id)

# =========================================================
#  GESTÃO (Produtos, Clientes, Equipe, Config)
# =========================================================
@login_required
def lista_produtos(request):
    produtos = Produto.objects.filter(empresa=request.user.empresa)
    return render(request, 'core/lista_produtos.html', {'produtos': produtos})

@login_required
def adicionar_produto(request):
    if request.method == 'POST':
        form = ProdutoForm(request.POST, request.FILES)
        if form.is_valid():
            produto = form.save(commit=False)
            produto.empresa = request.user.empresa
            produto.save()
            messages.success(request, "✅ Produto cadastrado!")
            return redirect('lista_produtos')
        else:
            messages.error(request, f"Erro ao cadastrar: {form.errors}")
    else:
        form = ProdutoForm()
    return render(request, 'core/form_produto.html', {'form': form, 'titulo': 'Novo Produto'})

@login_required
def editar_produto(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id, empresa=request.user.empresa)
    if request.method == 'POST':
        form = ProdutoForm(request.POST, request.FILES, instance=produto)
        if form.is_valid():
            form.save()
            return redirect('lista_produtos')
    else:
        form = ProdutoForm(instance=produto)
    return render(request, 'core/form_produto.html', {'form': form, 'titulo': 'Editar Produto'})

@login_required
def excluir_produto(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id, empresa=request.user.empresa)
    produto.delete()
    return redirect('lista_produtos')

@login_required
def configuracoes(request):
    if request.user.cargo == 'VENDEDOR': return HttpResponseForbidden("Acesso Negado")
    empresa = request.user.empresa
    
    if request.method == 'POST':
        form = ConfiguracaoEmpresaForm(request.POST, request.FILES, instance=empresa)
        if form.is_valid():
            form.save()
            # Lógica do Retorno Inteligente
            proximo_passo = request.POST.get('next')
            if proximo_passo == 'planos':
                return redirect('escolher_plano')
            return redirect('dashboard')
    else:
        form = ConfiguracaoEmpresaForm(instance=empresa)
    return render(request, 'core/configuracoes.html', {'form': form})

# =========================================================
#  OUTROS (Financeiro, Relatorios, Equipe, etc)
# =========================================================
# ... (Mantenha suas outras funções: financeiro, relatorios, lista_equipe, lista_clientes, etc.)
# Se você já tem elas no arquivo, elas ficarão aqui. Se não tiver, me avise que colo também.
# Para não ficar gigante, assumi que você vai manter o resto que já funcionava.
@login_required
def financeiro(request):
    if request.user.cargo == 'VENDEDOR': return HttpResponseForbidden("Acesso Negado")
    if not request.user.empresa.tem_acesso_financeiro(): return render(request, 'core/erro_plano.html')
    
    lancamentos = Lancamento.objects.filter(empresa=request.user.empresa).order_by('-data_vencimento')
    total_receitas = sum(l.valor for l in lancamentos if l.tipo == 'RECEITA' and l.pago)
    total_despesas = sum(l.valor for l in lancamentos if l.tipo == 'DESPESA' and l.pago)
    saldo = total_receitas - total_despesas
    return render(request, 'core/financeiro.html', locals())

@login_required
def adicionar_despesa(request):
    if request.method == 'POST':
        # Lógica simplificada (adicione form se quiser)
        Lancamento.objects.create(
            empresa=request.user.empresa,
            tipo='DESPESA',
            titulo=request.POST.get('titulo'),
            valor=request.POST.get('valor'),
            data_vencimento=request.POST.get('data_vencimento'),
            data_pagamento=request.POST.get('data_vencimento') if request.POST.get('pago') else None,
            pago=request.POST.get('pago') == 'on'
        )
        return redirect('financeiro')
    return render(request, 'core/adicionar_despesa.html')

@login_required
def relatorios(request):
    # ... (Use a lógica completa que te passei anteriormente para relatórios)
    return render(request, 'core/relatorios.html', {})

@login_required
def lista_equipe(request):
    usuarios = Usuario.objects.filter(empresa=request.user.empresa)
    return render(request, 'core/lista_equipe.html', {'usuarios': usuarios})

@login_required
def adicionar_colaborador(request):
    if request.user.cargo == 'VENDEDOR': return HttpResponseForbidden()
    # Verificação de Plano
    empresa = request.user.empresa
    if Usuario.objects.filter(empresa=empresa).count() >= empresa.limite_usuarios():
        messages.error(request, "Limite de usuários atingido.")
        return redirect('lista_equipe')

    if request.method == 'POST':
        form = UsuarioForm(request.POST)
        if form.is_valid():
            u = form.save(commit=False)
            u.empresa = empresa
            u.set_password(form.cleaned_data.get('senha') or '123456')
            u.save()
            return redirect('lista_equipe')
    else:
        form = UsuarioForm()
    return render(request, 'core/form_generico.html', {'form': form, 'titulo': 'Novo Colaborador'})

@login_required
def editar_colaborador(request, user_id):
    u = get_object_or_404(Usuario, id=user_id, empresa=request.user.empresa)
    if request.method == 'POST':
        form = UsuarioForm(request.POST, instance=u)
        if form.is_valid():
            u = form.save(commit=False)
            if form.cleaned_data.get('senha'): u.set_password(form.cleaned_data.get('senha'))
            u.save()
            return redirect('lista_equipe')
    else:
        form = UsuarioForm(instance=u)
    return render(request, 'core/form_generico.html', {'form': form, 'titulo': 'Editar'})

@login_required
def excluir_colaborador(request, user_id):
    u = get_object_or_404(Usuario, id=user_id, empresa=request.user.empresa)
    if u.id != request.user.id: u.delete()
    return redirect('lista_equipe')

@login_required
def lista_clientes(request):
    clientes = Cliente.objects.filter(empresa=request.user.empresa)
    return render(request, 'core/lista_clientes.html', {'clientes': clientes})

@login_required
def adicionar_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            c = form.save(commit=False)
            c.empresa = request.user.empresa
            c.save()
            return redirect('lista_clientes')
    else:
        form = ClienteForm()
    return render(request, 'core/form_generico.html', {'form': form, 'titulo': 'Novo Cliente'})

@login_required
def editar_cliente(request, id):
    c = get_object_or_404(Cliente, id=id, empresa=request.user.empresa)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=c)
        if form.is_valid():
            form.save()
            return redirect('lista_clientes')
    else:
        form = ClienteForm(instance=c)
    return render(request, 'core/form_generico.html', {'form': form, 'titulo': 'Editar Cliente'})

@login_required
def lista_fornecedores(request):
    fornecedores = Fornecedor.objects.filter(empresa=request.user.empresa)
    return render(request, 'core/lista_fornecedores.html', {'fornecedores': fornecedores})

@login_required
def adicionar_fornecedor(request):
    if request.method == 'POST':
        form = FornecedorForm(request.POST)
        if form.is_valid():
            f = form.save(commit=False)
            f.empresa = request.user.empresa
            f.save()
            return redirect('lista_fornecedores')
    else:
        form = FornecedorForm()
    return render(request, 'core/form_generico.html', {'form': form, 'titulo': 'Novo Fornecedor'})

@login_required
def lista_categorias(request):
    categorias = Categoria.objects.filter(empresa=request.user.empresa)
    return render(request, 'core/lista_categorias.html', {'categorias': categorias})

@login_required
def adicionar_categoria(request):
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            c = form.save(commit=False)
            c.empresa = request.user.empresa
            c.save()
            return redirect('lista_categorias')
    else:
        form = CategoriaForm()
    return render(request, 'core/form_generico.html', {'form': form, 'titulo': 'Nova Categoria'})

@login_required
def minhas_comissoes(request):
    # ... (Lógica das comissões)
    return render(request, 'core/minhas_comissoes.html', {})

@staff_member_required
def saas_painel(request):
    # ...
    return render(request, 'core/saas_painel.html', {})

@staff_member_required
def alternar_status_loja(request, empresa_id):
    # ...
    return redirect('saas_painel')

@staff_member_required
def gerar_contrato_pdf(request, empresa_id):
    # ...
    return HttpResponse("PDF") # Simplificado