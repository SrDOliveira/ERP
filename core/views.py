# core/views.py (VERSÃO COMPLETA COM DIAGNÓSTICO DE PAGAMENTO)

import os
import uuid
import requests
import json
import traceback # Importante para o erro

# Imports dos novos forms e models
from .models import Chamado, AjusteEstoque
from .forms import ChamadoForm, AjusteEstoqueForm
    # Servir arquivos de PWA
from django.views.generic import TemplateView

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
from .models import Chamado # Garanta que importou Chamado

from weasyprint import HTML

from .models import (
    Venda, ItemVenda, Produto, Cliente, Lancamento, Empresa, 
    MovimentoCaixa, Caixa, FormaPagamento, Usuario,
    Categoria, Fornecedor
)
from .forms import (
    ProdutoForm, AberturaCaixaForm, FechamentoCaixaForm,
    CategoriaForm, FornecedorForm, ClienteForm, 
    #ConfiguracaoEmpresaForm, UsuarioForm,
    CadastroLojaForm
)

# CONFIGURAÇÕES ASAAS
ASAAS_API_KEY = os.environ.get('ASAAS_API_KEY', '')
ASAAS_URL = os.environ.get('ASAAS_URL', 'https://www.asaas.com/api/v3')

# =========================================================
#  DASHBOARD & INICIO
# =========================================================
@login_required
def dashboard(request):
    empresa_usuario = request.user.empresa
    hoje = timezone.now().date()
    
    estoque_baixo_count = Produto.objects.filter(
        empresa=empresa_usuario, 
        estoque_atual__lte=F('estoque_minimo')
    ).count()

    vendas_hoje = Venda.objects.filter(empresa=empresa_usuario, data_venda__date=hoje, status='FECHADA')
    total_hoje = vendas_hoje.aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    qtd_vendas = vendas_hoje.count()
    
    datas_grafico = []
    valores_grafico = []
    for i in range(6, -1, -1):
        d = hoje - timedelta(days=i)
        val = Venda.objects.filter(empresa=empresa_usuario, status='FECHADA', data_venda__date=d).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
        datas_grafico.append(d.strftime('%d/%m'))
        valores_grafico.append(float(val))

    ultimas_vendas = Venda.objects.filter(empresa=empresa_usuario).order_by('-data_venda')[:5]

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

@login_required
def rota_inicial(request):
    if request.user.cargo in ['VENDEDOR', 'CAIXA']:
        return redirect('criar_venda')
    return redirect('dashboard')

# =========================================================
#  AUTO-CADASTRO
# =========================================================
def cadastro_loja(request):
    if request.method == 'POST':
        form = CadastroLojaForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            cnpj_provisorio = f"TEMP-{uuid.uuid4().hex[:8]}"

            # 1. Criar Empresa com o Ramo
            nova_empresa = Empresa.objects.create(
                nome_fantasia=data['nome_loja'],
                cnpj=cnpj_provisorio,
                ativa=True,
                data_vencimento=timezone.now().date() + timedelta(days=7),
                plano='ESSENCIAL',
                ramo_atividade=data['ramo'] # <--- SALVA O RAMO
            )
            
            novo_usuario = Usuario.objects.create_user(
                username=data['username'],
                email=data['email'],
                password=data['senha'],
                first_name=data['nome_usuario'],
                empresa=nova_empresa,
                cargo='GERENTE'
            )
            
            # 3. ONBOARDING INTELIGENTE (TEMPLATES)
            # Cria o básico para todos
            Caixa.objects.create(empresa=nova_empresa, nome="Caixa Principal")
            FormaPagamento.objects.create(empresa=nova_empresa, nome="Dinheiro", taxa=0)
            FormaPagamento.objects.create(empresa=nova_empresa, nome="Pix", taxa=0)
            
            # --- AQUI ENTRA A PERSONALIZAÇÃO POR NICHO ---
            
            if data['ramo'] == 'ROUPAS':
                # Cria categorias de moda
                Categoria.objects.create(empresa=nova_empresa, nome="Camisetas")
                Categoria.objects.create(empresa=nova_empresa, nome="Calças")
                Categoria.objects.create(empresa=nova_empresa, nome="Acessórios")
                Categoria.objects.create(empresa=nova_empresa, nome="Vestidos")
                
            elif data['ramo'] == 'MERCADO':
                # Cria categorias de mercado
                Categoria.objects.create(empresa=nova_empresa, nome="Bebidas")
                Categoria.objects.create(empresa=nova_empresa, nome="Mercearia")
                Categoria.objects.create(empresa=nova_empresa, nome="Limpeza")
                Categoria.objects.create(empresa=nova_empresa, nome="Hortifruti")
                
            elif data['ramo'] == 'SERVICOS':
                # Cria categorias de serviço
                Categoria.objects.create(empresa=nova_empresa, nome="Mão de Obra")
                Categoria.objects.create(empresa=nova_empresa, nome="Consultoria")
                Categoria.objects.create(empresa=nova_empresa, nome="Manutenção")
            
            # ... (seus ifs anteriores) ...

            elif data['ramo'] == 'SERVICOS':
                Categoria.objects.create(empresa=nova_empresa, nome="Mão de Obra")
                Categoria.objects.create(empresa=nova_empresa, nome="Consultoria")
                Categoria.objects.create(empresa=nova_empresa, nome="Manutenção")
            
            else:
                # Caso ele escolha "Outros" ou algo novo
                Categoria.objects.create(empresa=nova_empresa, nome="Geral")
                Categoria.objects.create(empresa=nova_empresa, nome="Novidades")
            
            login(request, novo_usuario)
            messages.success(request, f"Bem-vindo ao Nexum! Sua loja foi criada.")
            return redirect('escolher_plano')
    else:
        form = CadastroLojaForm()
    return render(request, 'core/signup.html', {'form': form})

@login_required
def escolher_plano(request):
    return render(request, 'core/planos.html')

# =========================================================
#  PAGAMENTOS E ASSINATURA (ASAAS) - VERSÃO CORRIGIDA
# =========================================================
@login_required
def iniciar_pagamento(request, plano):
    empresa = request.user.empresa
    
    if "TEMP-" in empresa.cnpj or len(empresa.cnpj) < 11:
        messages.warning(request, "⚠️ Para assinar, precisamos do seu CPF/CNPJ real. Atualize abaixo.")
        return redirect('/configuracoes/?next=planos')

    if plano == 'ESSENCIAL': valor = 129.00
    elif plano == 'PRO': valor = 249.00
    else: return redirect('dashboard')

    if not ASAAS_API_KEY:
        messages.error(request, "Erro: Chave de pagamento não configurada.")
        return redirect('dashboard')

    headers = {"Content-Type": "application/json", "access_token": ASAAS_API_KEY}

    # 1. Cliente
    if not empresa.asaas_customer_id:
        payload_cliente = { "name": empresa.nome_fantasia, "cpfCnpj": empresa.cnpj, "email": request.user.email }
        try:
            res = requests.post(f"{ASAAS_URL}/customers", json=payload_cliente, headers=headers)
            if res.status_code == 200:
                empresa.asaas_customer_id = res.json()['id']
                empresa.save()
            else:
                # Tenta recuperar se já existe
                res_busca = requests.get(f"{ASAAS_URL}/customers?cpfCnpj={empresa.cnpj}", headers=headers)
                if res_busca.json().get('data'):
                    empresa.asaas_customer_id = res_busca.json()['data'][0]['id']
                    empresa.save()
                else:
                    messages.error(request, "Erro ao cadastrar cliente no Asaas.")
                    return redirect('dashboard')
        except:
            messages.error(request, "Erro de conexão.")
            return redirect('dashboard')

    # 2. Assinatura
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
        
        sub_id = None
        if response.status_code == 200:
            sub_id = response.json()['id']
        elif 'unique' in response.text: # Já existe
            res_lista = requests.get(f"{ASAAS_URL}/subscriptions?customer={empresa.asaas_customer_id}&status=ACTIVE", headers=headers)
            if res_lista.json().get('data'):
                sub_id = res_lista.json()['data'][0]['id']
        
        if sub_id:
            # 3. Buscar Cobrança (O Pulo do Gato)
            import time
            time.sleep(0.5)
            pagamentos_res = requests.get(f"{ASAAS_URL}/subscriptions/{sub_id}/payments", headers=headers)
            
            if pagamentos_res.status_code == 200:
                lista = pagamentos_res.json().get('data', [])
                for cobranca in lista:
                    if cobranca['status'] == 'PENDING':
                        return redirect(cobranca['invoiceUrl']) # <--- CORREÇÃO AQUI
            
            messages.warning(request, "Assinatura ativa! O boleto foi enviado para seu e-mail.")
            return redirect('dashboard')
        else:
            messages.error(request, "Não foi possível gerar a assinatura.")
            return redirect('dashboard')

    except Exception as e:
        messages.error(request, f"Erro técnico: {str(e)}")
        return redirect('dashboard')

@csrf_exempt 
def webhook_asaas(request):
    # ... (Mantenha a função webhook igual, ela estava correta)
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
                    val = float(payment.get('value', 0))
                    if val >= 249: empresa.plano = 'PRO'
                    else: empresa.plano = 'ESSENCIAL'
                    empresa.save()
                    return JsonResponse({'status': 'ok'})
                except Empresa.DoesNotExist:
                    return JsonResponse({'status': '404'})
            return JsonResponse({'status': 'ignorado'})
        except:
            return JsonResponse({'status': 'erro'}, status=500)
    return HttpResponseForbidden()

# =========================================================
#  CAIXA E PDV
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
            mov = form.save(commit=False)
            mov.empresa = request.user.empresa
            mov.operador = request.user
            mov.save()
            return redirect('criar_venda')
    else:
        form = AberturaCaixaForm(request.user)
    return render(request, 'core/form_abrir_caixa.html', {'form': form})

@login_required
def fechar_caixa(request, movimento_id):
    mov = get_object_or_404(MovimentoCaixa, id=movimento_id, operador=request.user, status='ABERTO')
    total_vendido = mov.vendas.filter(status='FECHADA').aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    valor_esperado = mov.valor_abertura + total_vendido

    if request.method == 'POST':
        form = FechamentoCaixaForm(request.user, request.POST, instance=mov)
        if form.is_valid():
            mov = form.save(commit=False)
            mov.status = 'FECHADO'
            mov.data_fechamento = timezone.now()
            mov.diferenca = mov.valor_fechamento - valor_esperado
            mov.save()
            return redirect('dashboard')
    else:
        form = FechamentoCaixaForm(request.user, instance=mov)
    return render(request, 'core/form_fechar_caixa.html', {'form': form, 'movimento': mov, 'total_vendido': total_vendido, 'valor_esperado': valor_esperado})

@login_required
def criar_venda(request):
    caixa_aberto = MovimentoCaixa.objects.filter(operador=request.user, status='ABERTO').first()
    if not caixa_aberto:
        return render(request, 'core/erro_caixa_fechado.html')

    venda = Venda.objects.create(
        empresa=request.user.empresa,
        vendedor=request.user,
        cliente=Cliente.objects.filter(empresa=request.user.empresa).first(),
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
            forma_id = request.POST.get('forma_pagamento')
            if forma_id:
                venda.valor_total = sum(i.subtotal for i in venda.itens.all())
                venda.status = 'FECHADA'
                venda.forma_pagamento_id = forma_id
                venda.save()
                
                if venda.cliente:
                    venda.cliente.data_ultima_compra = timezone.now()
                    venda.cliente.save()
                
                for item in venda.itens.all():
                    item.produto.estoque_atual -= item.quantidade
                    item.produto.save()

                if request.POST.get('emitir_fiscal'):
                    venda.nota_fiscal_emitida = True
                    venda.save()
                    messages.success(request, "Venda Fechada (Nota Fiscal em processamento).")
                else:
                    messages.success(request, "Venda Fechada com sucesso.")

                Lancamento.objects.create(
                    empresa=venda.empresa, tipo='RECEITA',
                    titulo=f"Venda #{venda.id}", valor=venda.valor_total,
                    data_vencimento=timezone.now().date(), data_pagamento=timezone.now().date(),
                    pago=True, venda_origem=venda
                )
                return redirect('dashboard')

    template = 'core/pdv_focus.html' if request.user.cargo in ['VENDEDOR', 'CAIXA'] else 'core/pdv.html'
    
    return render(request, template, {
        'venda': venda,
        'produtos': Produto.objects.filter(empresa=request.user.empresa, ativo=True),
        'clientes': Cliente.objects.filter(empresa=request.user.empresa),
        'formas_pagamento': FormaPagamento.objects.filter(empresa=request.user.empresa),
        'total': sum(item.subtotal for item in venda.itens.all())
    })

@login_required
@require_POST
def adicionar_item(request, venda_id):
    venda = get_object_or_404(Venda, id=venda_id)
    prod_id = request.POST.get('produto')
    qtd = int(request.POST.get('quantidade', 1))
    if prod_id:
        p = get_object_or_404(Produto, id=prod_id)
        ItemVenda.objects.create(venda=venda, produto=p, quantidade=qtd, preco_unitario=p.preco_venda)
    return redirect('pdv', venda_id=venda.id)

# =========================================================
#  GESTÃO, RELATÓRIOS E PAINEL ESTOQUE (CORRIGIDO)
# =========================================================
@login_required
def painel_estoque(request):
    produtos = Produto.objects.filter(empresa=request.user.empresa)
    baixo_estoque = produtos.filter(estoque_atual__lte=F('estoque_minimo'))
    total_custo = sum(p.estoque_atual * p.preco_custo for p in produtos)
    total_venda = sum(p.estoque_atual * p.preco_venda for p in produtos)
    lucro_potencial = total_venda - total_custo
    
    lista_inteligente = []
    inicio_mes = timezone.now().date() - timedelta(days=30)
    for p in produtos:
        qtd = ItemVenda.objects.filter(produto=p, venda__status='FECHADA', venda__data_venda__date__gte=inicio_mes).aggregate(Sum('quantidade'))['quantidade__sum'] or 0
        dias = int(p.estoque_atual / (qtd/30)) if qtd > 0 else 999
        lista_inteligente.append({'nome': p.nome, 'atual': p.estoque_atual, 'vendidos_30d': qtd, 'dias_restantes': dias})
    
    lista_inteligente.sort(key=lambda x: x['dias_restantes'])
    return render(request, 'core/painel_estoque.html', {'baixo_estoque': baixo_estoque, 'total_custo': total_custo, 'total_venda': total_venda, 'lucro_potencial': lucro_potencial, 'lista_inteligente': lista_inteligente[:10], 'total_produtos': produtos.count()})

@login_required
def lista_produtos(request):
    return render(request, 'core/lista_produtos.html', {'produtos': Produto.objects.filter(empresa=request.user.empresa)})

@login_required
def adicionar_produto(request):
    if request.method == 'POST':
        form = ProdutoForm(request.POST, request.FILES)
        if form.is_valid():
            p = form.save(commit=False)
            p.empresa = request.user.empresa
            p.save()
            messages.success(request, "✅ Produto cadastrado!")
            return redirect('lista_produtos')
        else:
            messages.error(request, f"Erro: {form.errors}")
    else:
        form = ProdutoForm()
    return render(request, 'core/form_produto.html', {'form': form, 'titulo': 'Novo Produto'})

@login_required
def editar_produto(request, produto_id):
    p = get_object_or_404(Produto, id=produto_id, empresa=request.user.empresa)
    if request.method == 'POST':
        form = ProdutoForm(request.POST, request.FILES, instance=p)
        if form.is_valid():
            form.save()
            return redirect('lista_produtos')
    else:
        form = ProdutoForm(instance=p)
    return render(request, 'core/form_produto.html', {'form': form, 'titulo': 'Editar Produto'})

@login_required
def excluir_produto(request, produto_id):
    p = get_object_or_404(Produto, id=produto_id, empresa=request.user.empresa)
    p.delete()
    return redirect('lista_produtos')
'''
@login_required
def configuracoes(request):
    if request.user.cargo == 'VENDEDOR': return HttpResponseForbidden()
    empresa = request.user.empresa
    if request.method == 'POST':
        form = ConfiguracaoEmpresaForm(request.POST, request.FILES, instance=empresa)
        if form.is_valid():
            form.save()
            if request.POST.get('next') == 'planos': return redirect('escolher_plano')
            return redirect('dashboard')
    else:
        form = ConfiguracaoEmpresaForm(instance=empresa)
    return render(request, 'core/configuracoes.html', {'form': form})
'''
@login_required
def financeiro(request):
    # Vendedor continua bloqueado
    if request.user.cargo == 'VENDEDOR': return HttpResponseForbidden("Acesso Negado")
    
    # MUDANÇA AQUI:
    # Se NÃO for Superusuário E a empresa NÃO tiver acesso, aí sim bloqueia.
    # (Ou seja: Se for superusuário, ele pula esse if e entra)
    if not request.user.is_superuser and not request.user.empresa.tem_acesso_financeiro(): 
        return render(request, 'core/erro_plano.html')
    
@login_required
def adicionar_despesa(request):
    if request.method == 'POST':
        Lancamento.objects.create(
            empresa=request.user.empresa, tipo='DESPESA',
            titulo=request.POST.get('titulo'), valor=request.POST.get('valor'),
            data_vencimento=request.POST.get('data_vencimento'),
            data_pagamento=request.POST.get('data_vencimento') if request.POST.get('pago') else None,
            pago=request.POST.get('pago') == 'on'
        )
        return redirect('financeiro')
    return render(request, 'core/adicionar_despesa.html')

@login_required
def relatorios(request):
    if request.user.cargo == 'VENDEDOR': return HttpResponseForbidden()
    
    # ADICIONE A MESMA TRAVA INTELIGENTE AQUI:
    if not request.user.is_superuser and not request.user.empresa.tem_acesso_financeiro():
        return render(request, 'core/erro_plano.html')
    hoje = timezone.now().date()
    data_ini = request.GET.get('data_ini', hoje.replace(day=1).strftime('%Y-%m-%d'))
    data_fim = request.GET.get('data_fim', hoje.strftime('%Y-%m-%d'))
    tipo = request.GET.get('tipo', 'vendas')
    contexto = {'data_ini': data_ini, 'data_fim': data_fim, 'tipo': tipo}
    if tipo == 'vendas':
        vendas = Venda.objects.filter(empresa=request.user.empresa, status='FECHADA', data_venda__date__range=[data_ini, data_fim])
        contexto.update({'vendas': vendas, 'total_periodo': vendas.aggregate(Sum('valor_total'))['valor_total__sum'] or 0, 'qtd_vendas': vendas.count()})
    elif tipo == 'financeiro':
        lancamentos = Lancamento.objects.filter(empresa=request.user.empresa, data_pagamento__range=[data_ini, data_fim], pago=True)
        rec = lancamentos.filter(tipo='RECEITA').aggregate(Sum('valor'))['valor__sum'] or 0
        desp = lancamentos.filter(tipo='DESPESA').aggregate(Sum('valor'))['valor__sum'] or 0
        contexto.update({'lancamentos': lancamentos, 'total_receitas': rec, 'total_despesas': desp, 'lucro': rec - desp})
    elif tipo == 'produtos':
        itens = ItemVenda.objects.filter(venda__empresa=request.user.empresa, venda__status='FECHADA', venda__data_venda__date__range=[data_ini, data_fim]).values('produto__nome').annotate(qtd_vendida=Sum('quantidade'), total_vendido=Sum(F('quantidade')*F('preco_unitario'))).order_by('-qtd_vendida')
        contexto['ranking_produtos'] = itens
    return render(request, 'core/relatorios.html', contexto)

@login_required
def lista_equipe(request):
    return render(request, 'core/lista_equipe.html', {'usuarios': Usuario.objects.filter(empresa=request.user.empresa)})

@login_required
def adicionar_colaborador(request):
    if request.user.cargo == 'VENDEDOR': return HttpResponseForbidden()
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
    else: form = UsuarioForm()
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
    else: form = UsuarioForm(instance=u)
    return render(request, 'core/form_generico.html', {'form': form, 'titulo': 'Editar'})

@login_required
def excluir_colaborador(request, user_id):
    u = get_object_or_404(Usuario, id=user_id, empresa=request.user.empresa)
    if u.id != request.user.id: u.delete()
    return redirect('lista_equipe')

@login_required
def lista_clientes(request):
    return render(request, 'core/lista_clientes.html', {'clientes': Cliente.objects.filter(empresa=request.user.empresa)})

@login_required
def adicionar_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            c = form.save(commit=False)
            c.empresa = request.user.empresa
            c.save()
            return redirect('lista_clientes')
    else: form = ClienteForm()
    return render(request, 'core/form_generico.html', {'form': form, 'titulo': 'Novo Cliente'})

@login_required
def editar_cliente(request, id):
    c = get_object_or_404(Cliente, id=id, empresa=request.user.empresa)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=c)
        if form.is_valid():
            form.save()
            return redirect('lista_clientes')
    else: form = ClienteForm(instance=c)
    return render(request, 'core/form_generico.html', {'form': form, 'titulo': 'Editar Cliente'})

@login_required
def lista_fornecedores(request):
    return render(request, 'core/lista_fornecedores.html', {'fornecedores': Fornecedor.objects.filter(empresa=request.user.empresa)})

@login_required
def adicionar_fornecedor(request):
    if request.method == 'POST':
        form = FornecedorForm(request.POST)
        if form.is_valid():
            f = form.save(commit=False)
            f.empresa = request.user.empresa
            f.save()
            return redirect('lista_fornecedores')
    else: form = FornecedorForm()
    return render(request, 'core/form_generico.html', {'form': form, 'titulo': 'Novo Fornecedor'})

@login_required
def lista_categorias(request):
    return render(request, 'core/lista_categorias.html', {'categorias': Categoria.objects.filter(empresa=request.user.empresa)})

@login_required
def adicionar_categoria(request):
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            c = form.save(commit=False)
            c.empresa = request.user.empresa
            c.save()
            return redirect('lista_categorias')
    else: form = CategoriaForm()
    return render(request, 'core/form_generico.html', {'form': form, 'titulo': 'Nova Categoria'})

@login_required
def minhas_comissoes(request):
    itens = ItemVenda.objects.filter(venda__empresa=request.user.empresa, venda__status='FECHADA').order_by('-venda__data_venda')
    if request.user.cargo == 'VENDEDOR': itens = itens.filter(venda__vendedor=request.user)
    total_comissao = sum(i.comissao_valor for i in itens)
    total_vendido = sum(i.subtotal for i in itens)
    return render(request, 'core/minhas_comissoes.html', {'itens': itens, 'total_comissao': total_comissao, 'total_vendido': total_vendido})

@staff_member_required
def saas_painel(request):
    empresas = Empresa.objects.all().order_by('-data_criacao')
    
    # Busca chamados (Ordena: Abertos primeiro, depois os mais novos)
    chamados = Chamado.objects.all().order_by('status', '-data_abertura')
    
    total_lojas = empresas.count()
    lojas_ativas = empresas.filter(ativa=True).count()
    chamados_abertos = chamados.filter(status='ABERTO').count()
    
    return render(request, 'core/saas_painel.html', {
        'empresas': empresas,
        'chamados': chamados, # Enviando a lista para o HTML
        'total_lojas': total_lojas,
        'lojas_ativas': lojas_ativas,
        'chamados_abertos': chamados_abertos
    })

@staff_member_required
def responder_chamado(request, chamado_id):
    chamado = get_object_or_404(Chamado, id=chamado_id)
    
    if request.method == 'POST':
        resposta = request.POST.get('resposta')
        if resposta:
            chamado.resposta_admin = resposta
            chamado.status = 'RESOLVIDO'
            chamado.save()
            messages.success(request, f"Chamado #{chamado.id} respondido com sucesso!")
            return redirect('saas_painel')
            
    return render(request, 'core/form_responder_chamado.html', {'chamado': chamado})

@staff_member_required
def gerar_contrato_pdf(request, empresa_id):
    empresa = get_object_or_404(Empresa, id=empresa_id)
    contexto = {'empresa': empresa, 'data_atual': timezone.now(), 'contratada': 'NEXUM ERP LTDA', 'cnpj_contratada': '00.000.000/0001-00'}
    html_string = render_to_string('core/contrato_saas.html', contexto)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Contrato_{empresa.nome_fantasia}.pdf"'
    HTML(string=html_string).write_pdf(response)
    return response

@login_required
def gerar_orcamento_pdf(request, venda_id):
    venda = get_object_or_404(Venda, id=venda_id)
    total = sum(item.subtotal for item in venda.itens.all())
    html_string = render_to_string('core/orcamento_pdf.html', {'venda': venda, 'total_calculado': total})
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="orcamento_{venda.id}.pdf"'
    HTML(string=html_string).write_pdf(response)
    return response

@login_required
def imprimir_cupom(request, venda_id):
    venda = get_object_or_404(Venda, id=venda_id, empresa=request.user.empresa)
    return render(request, 'core/cupom.html', {'venda': venda})

@login_required
def catalogo_qr(request):
    return render(request, 'core/catalogo_qr.html', {'produtos': Produto.objects.filter(empresa=request.user.empresa)})

# Adicione este import no topo
from django.contrib.auth.views import LoginView

# ... (outras views)

class CustomLoginView(LoginView):
    template_name = 'core/login.html'
    
    def form_valid(self, form):
        # Chama a lógica padrão de login
        result = super().form_valid(form)
        
        # Verifica se marcou a caixinha
        remember_me = self.request.POST.get('remember_me')
        
        if remember_me:
            # Se marcou: Sessão dura 2 semanas (padrão Django) ou o que estiver no settings
            self.request.session.set_expiry(1209600) # 2 semanas em segundos
        else:
            # Se NÃO marcou: Sessão expira ao fechar o navegador
            self.request.session.set_expiry(0)
            
        return result
    
class ServiceWorkerView(TemplateView):
    template_name = "core/sw.js"
    content_type = "application/javascript"
    name = "sw.js"

class ManifestView(TemplateView):
    template_name = "core/manifest.json" # Vamos criar um template pra ele tbm pra facilitar
    content_type = "application/json"
    name = "manifest.json"

    # =========================================================
#  PWA (ANDROID APP)
# =========================================================
class ServiceWorkerView(TemplateView):
    template_name = "core/sw.js"
    content_type = "application/javascript"
    name = "sw.js"

class ManifestView(TemplateView):
    template_name = "core/manifest.json"
    content_type = "application/json"
    name = "manifest.json"


# --- SUPORTE ---
@login_required
def suporte(request):
    chamados = Chamado.objects.filter(usuario=request.user).order_by('-data_abertura')
    
    if request.method == 'POST':
        form = ChamadoForm(request.POST, request.FILES)
        if form.is_valid():
            chamado = form.save(commit=False)
            chamado.usuario = request.user
            chamado.save()
            messages.success(request, "Chamado aberto! Responderemos em breve.")
            return redirect('suporte')
    else:
        form = ChamadoForm()
        
    return render(request, 'core/suporte.html', {'form': form, 'chamados': chamados})

# --- GESTÃO DE PERDAS / AJUSTES ---
@login_required
def ajuste_estoque(request):
    if request.user.cargo == 'VENDEDOR': return HttpResponseForbidden()
    
    ajustes = AjusteEstoque.objects.filter(empresa=request.user.empresa).order_by('-data_ajuste')[:20]
    
    if request.method == 'POST':
        form = AjusteEstoqueForm(request.user, request.POST)
        if form.is_valid():
            ajuste = form.save(commit=False)
            ajuste.empresa = request.user.empresa
            ajuste.responsavel = request.user
            
            # Lógica do Estoque:
            # Se for ENTRADA, soma. Se for qualquer outro motivo (Perda, Defeito), subtrai.
            prod = ajuste.produto
            qtd = abs(ajuste.quantidade) # Garante número positivo pra lógica
            
            if ajuste.motivo == 'ENTRADA':
                prod.estoque_atual += qtd
                msg = f"Adicionado {qtd} ao estoque."
            else:
                prod.estoque_atual -= qtd
                msg = f"Removido {qtd} do estoque."
            
            prod.save()
            ajuste.save()
            messages.success(request, msg)
            return redirect('ajuste_estoque')
    else:
        form = AjusteEstoqueForm(request.user)
        
    return render(request, 'core/ajuste_estoque.html', {'form': form, 'ajustes': ajustes})