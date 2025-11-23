# core/views.py

# --- 1. IMPORTS GERAIS E DJANGO ---
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth import login # <--- Necessário para o Auto-Login
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count, F, Avg, Q, ExpressionWrapper, FloatField
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

# --- 2. IMPORTS DE TERCEIROS ---
from weasyprint import HTML

# --- 3. IMPORTS DOS SEUS MODELOS ---
from .models import (
    Venda, ItemVenda, Produto, Cliente, Lancamento, Empresa, 
    MovimentoCaixa, Caixa, FormaPagamento, Usuario,
    Categoria, Fornecedor
)

# --- 4. IMPORTS DOS SEUS FORMULÁRIOS ---
from .forms import (
    ProdutoForm, AberturaCaixaForm, FechamentoCaixaForm,
    CategoriaForm, FornecedorForm, ClienteForm, 
    ConfiguracaoEmpresaForm, UsuarioForm,
    CadastroLojaForm  # <--- O NOVO FORMULÁRIO FICA AQUI
)

# =========================================================
#  Abaixo começam as funções...
# =========================================================

# =========================================================
#  Abaixo começam as funções (dashboard, pdv, etc...)
# =========================================================
# Biblioteca de PDF
from weasyprint import HTML

# --- 3. IMPORTS DOS SEUS MODELOS E FORMS ---
from .models import (
    Venda, ItemVenda, Produto, Cliente, Lancamento, Empresa, 
    MovimentoCaixa, Caixa, FormaPagamento, Usuario,
    Categoria, Fornecedor  # <--- ADICIONE ESTES DOIS AQUI
)
from .forms import (
    ProdutoForm, AberturaCaixaForm, FechamentoCaixaForm,
    CategoriaForm, FornecedorForm, ClienteForm, ConfiguracaoEmpresaForm # <--- Novo
)

# =========================================================
#  DASHBOARD
# =========================================================
@login_required
def dashboard(request):
    empresa = request.user.empresa
    hoje = timezone.now().date()
    ontem = hoje - timedelta(days=1)
    inicio_mes = hoje.replace(day=1)
    sete_dias_atras = hoje - timedelta(days=7)
    sessenta_dias_atras = hoje - timedelta(days=60)

    # --- NÍVEL 1: VISÃO IMEDIATA (HOJE) ---
    vendas_hoje = Venda.objects.filter(empresa=empresa, data_venda__date=hoje, status='FECHADA')
    vendas_ontem = Venda.objects.filter(empresa=empresa, data_venda__date=ontem, status='FECHADA')
    
    total_hoje = vendas_hoje.aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    total_ontem = vendas_ontem.aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    
    # Comparativo (Crescimento)
    crescimento_dia = 0
    if total_ontem > 0:
        crescimento_dia = ((total_hoje - total_ontem) / total_ontem) * 100

    ticket_medio = vendas_hoje.aggregate(Avg('valor_total'))['valor_total__avg'] or 0
    qtd_itens_hoje = ItemVenda.objects.filter(venda__in=vendas_hoje).aggregate(Sum('quantidade'))['quantidade__sum'] or 0
    
    # Caixas Abertos
    caixas_abertos = MovimentoCaixa.objects.filter(empresa=empresa, status='ABERTO').count()
    
    # Estoque Crítico
    estoque_critico = Produto.objects.filter(empresa=empresa, estoque_atual__lte=F('estoque_minimo')).count()

    # --- NÍVEL 2: SITUAÇÃO FINANCEIRA ---
    # Contas a Pagar Hoje (Que não foram pagas)
    contas_pagar_hoje = Lancamento.objects.filter(
        empresa=empresa, tipo='DESPESA', data_vencimento=hoje, pago=False
    ).aggregate(Sum('valor'))['valor__sum'] or 0
    
    # Contas a Receber Hoje (Vendas a prazo, se houver, ou boletos)
    contas_receber_hoje = Lancamento.objects.filter(
        empresa=empresa, tipo='RECEITA', data_vencimento=hoje, pago=False
    ).aggregate(Sum('valor'))['valor__sum'] or 0
    
    saldo_do_dia = total_hoje - contas_pagar_hoje # Simplificado (Caixa gerado - Contas a pagar)

    # --- NÍVEL 3: CHECKLIST DE AÇÕES URGENTES ---
    alertas = []
    if estoque_critico > 0:
        alertas.append({'msg': f'{estoque_critico} produtos com estoque baixo/zerado', 'tipo': 'danger', 'link': 'lista_produtos'})
    if caixas_abertos == 0 and total_hoje == 0: # Se não vendeu nada e não tem caixa aberto
        alertas.append({'msg': 'Nenhum caixa aberto no momento', 'tipo': 'warning', 'link': 'abrir_caixa'})
    if contas_pagar_hoje > 0:
        alertas.append({'msg': f'R$ {contas_pagar_hoje} em contas vencendo hoje', 'tipo': 'danger', 'link': 'financeiro'})
    
    # Clientes VIP Inativos (Compraram muito no passado, mas nada nos últimos 60 dias)
    # Lógica simplificada: Clientes que não compram há 60 dias
    clientes_inativos = Cliente.objects.filter(
        empresa=empresa, 
        data_ultima_compra__lt=sessenta_dias_atras
    ).count()
    if clientes_inativos > 0:
        alertas.append({'msg': f'{clientes_inativos} clientes inativos há +60 dias', 'tipo': 'info', 'link': 'lista_clientes'})

    # --- NÍVEL 4: RANKINGS ---
    # Mais Vendidos (7 dias)
    top_produtos = ItemVenda.objects.filter(
        venda__empresa=empresa, venda__status='FECHADA', venda__data_venda__date__gte=sete_dias_atras
    ).values('produto__nome').annotate(qtd=Sum('quantidade')).order_by('-qtd')[:5]
    
    # Produtos "Encalhados" (Sem vendas nos últimos 60 dias, mas com estoque > 0)
    # Essa query é pesada, vamos simplificar: Produtos com estoque mas sem venda recente
    produtos_com_estoque = Produto.objects.filter(empresa=empresa, estoque_atual__gt=0)
    produtos_encalhados = []
    for p in produtos_com_estoque:
        vendeu_recente = ItemVenda.objects.filter(
            produto=p, venda__data_venda__date__gte=sessenta_dias_atras
        ).exists()
        if not vendeu_recente:
            produtos_encalhados.append(p)
            if len(produtos_encalhados) >= 5: break # Pega só 5 pra não travar

    # --- NÍVEL 5: GRÁFICOS (DADOS JSON) ---
    # Vendas dos últimos 7 dias
    datas_grafico = []
    valores_grafico = []
    for i in range(6, -1, -1):
        d = hoje - timedelta(days=i)
        val = Venda.objects.filter(empresa=empresa, status='FECHADA', data_venda__date=d).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
        datas_grafico.append(d.strftime('%d/%m'))
        valores_grafico.append(float(val))

    return render(request, 'core/index.html', {
        # Nível 1
        'total_hoje': total_hoje,
        'crescimento_dia': crescimento_dia,
        'ticket_medio': ticket_medio,
        'qtd_itens_hoje': qtd_itens_hoje,
        'caixas_abertos': caixas_abertos,
        'estoque_critico': estoque_critico,
        
        # Nível 2
        'contas_pagar_hoje': contas_pagar_hoje,
        'contas_receber_hoje': contas_receber_hoje,
        'saldo_do_dia': saldo_do_dia,
        
        # Nível 3
        'alertas': alertas,
        
        # Nível 4
        'top_produtos': top_produtos,
        'produtos_encalhados': produtos_encalhados,
        
        # Nível 5 (Gráficos)
        'datas_grafico': datas_grafico,
        'valores_grafico': valores_grafico,
        
        # Extras
        'total_clientes': Cliente.objects.filter(empresa=empresa).count()
    })

# =========================================================
#  CONTROLE DE CAIXA (TURNOS)
# =========================================================
@login_required
def gerenciar_caixa(request):
    caixa_aberto = MovimentoCaixa.objects.filter(operador=request.user, status='ABERTO').first()
    if caixa_aberto:
        return render(request, 'core/caixa_aberto.html', {'movimento': caixa_aberto})
    return redirect('criar_venda')

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
            return redirect('dashboard')
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
    # Verifica Caixa Aberto
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
        
        # 1. Troca de Cliente
        if request.POST.get('cliente'):
            venda.cliente_id = request.POST.get('cliente')
            venda.save()
            
        # 2. Fechar Venda
        if acao == 'fechar_venda':
            forma_pagto_id = request.POST.get('forma_pagamento')
            
            if forma_pagto_id:
                # --- A. ATUALIZA A VENDA ---
                total = sum(item.subtotal for item in venda.itens.all())
                venda.valor_total = total
                venda.status = 'FECHADA'
                venda.forma_pagamento_id = forma_pagto_id
                venda.save()
                
                # --- B. ATUALIZA O CLIENTE (DATA DA ÚLTIMA COMPRA) ---
                if venda.cliente:
                    venda.cliente.data_ultima_compra = timezone.now()
                    venda.cliente.save()
                
                # --- C. BAIXA ESTOQUE ---
                for item in venda.itens.all():
                    p = item.produto
                    p.estoque_atual -= item.quantidade
                    p.save()

                # --- D. INTEGRAÇÃO FISCAL (Lógica da escolha) ---
                quer_nota = request.POST.get('emitir_fiscal') # Vem 'on' ou None
                
                if quer_nota:
                    try:
                        # Aqui entraria a chamada real da API Fiscal
                        # Ex: api.emitir_nfce(venda)
                        venda.nota_fiscal_emitida = True
                        venda.save()
                        messages.success(request, "Venda Fechada! Nota Fiscal enviada para processamento.")
                    except Exception as e:
                        messages.error(request, f"Venda gravada, mas erro na Nota: {e}")
                else:
                    messages.success(request, "Venda Fechada com sucesso (Sem valor fiscal).")

                # --- E. LANÇA NO FINANCEIRO ---
                # (Note que está FORA do if/else da nota, mas DENTRO do if forma_pagto)
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
                
                # --- F. REDIRECIONA ---
                return redirect('dashboard')

    # Dados para o Template
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
#  GESTÃO DE PRODUTOS
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
            return redirect('lista_produtos')
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

# =========================================================
#  FINANCEIRO
# =========================================================
@login_required
def financeiro(request):
    # Bloqueio de Vendedor
    if request.user.cargo == 'VENDEDOR':
        return HttpResponseForbidden("Acesso Negado: Área restrita à gerência.")

    lancamentos = Lancamento.objects.filter(empresa=request.user.empresa).order_by('-data_vencimento')
    total_receitas = sum(l.valor for l in lancamentos if l.tipo == 'RECEITA' and l.pago)
    total_despesas = sum(l.valor for l in lancamentos if l.tipo == 'DESPESA' and l.pago)
    saldo = total_receitas - total_despesas

    return render(request, 'core/financeiro.html', {
        'lancamentos': lancamentos,
        'saldo': saldo,
        'total_receitas': total_receitas,
        'total_despesas': total_despesas
    })

@login_required
def adicionar_despesa(request):
    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        valor = request.POST.get('valor')
        data_vencimento = request.POST.get('data_vencimento')
        pago = request.POST.get('pago') == 'on'
        
        Lancamento.objects.create(
            empresa=request.user.empresa,
            tipo='DESPESA',
            titulo=titulo,
            valor=valor,
            data_vencimento=data_vencimento,
            data_pagamento=data_vencimento if pago else None,
            pago=pago
        )
        return redirect('financeiro')
    return render(request, 'core/adicionar_despesa.html')

# =========================================================
#  RELATÓRIOS E PDFS
# =========================================================
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
    produtos = Produto.objects.filter(empresa=request.user.empresa)
    return render(request, 'core/catalogo_qr.html', {'produtos': produtos})

# =========================================================
#  PAINEL DO DONO DO SAAS (ADMIN MESTRE)
# =========================================================
@staff_member_required
def saas_painel(request):
    empresas = Empresa.objects.all().order_by('-data_criacao')
    total_lojas = empresas.count()
    lojas_ativas = empresas.filter(ativa=True).count()
    return render(request, 'core/saas_painel.html', {
        'empresas': empresas,
        'total_lojas': total_lojas,
        'lojas_ativas': lojas_ativas
    })

@staff_member_required
def alternar_status_loja(request, empresa_id):
    empresa = get_object_or_404(Empresa, id=empresa_id)
    empresa.ativa = not empresa.ativa
    empresa.save()
    return redirect('saas_painel')

@staff_member_required
def gerar_contrato_pdf(request, empresa_id):
    empresa = get_object_or_404(Empresa, id=empresa_id)
    contexto = {
        'empresa': empresa,
        'data_atual': timezone.now(),
        'contratada': 'SEU NOME SOFTWARE LTDA',
        'cnpj_contratada': '00.000.000/0001-00',
    }
    html_string = render_to_string('core/contrato_saas.html', contexto)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Contrato_{empresa.nome_fantasia}.pdf"'
    HTML(string=html_string).write_pdf(response)
    return response

# --- GESTÃO DE COMISSÕES ---
@login_required
def minhas_comissoes(request):
    # 1. Filtro Básico: Vendas Fechadas da Empresa
    itens = ItemVenda.objects.filter(
        venda__empresa=request.user.empresa, 
        venda__status='FECHADA'
    ).order_by('-venda__data_venda')

    # 2. Se for VENDEDOR, restringe apenas aos dele
    if request.user.cargo == 'VENDEDOR':
        itens = itens.filter(venda__vendedor=request.user)
    
    # 3. Filtros de Data (se o usuário preencheu)
    data_ini = request.GET.get('data_ini')
    data_fim = request.GET.get('data_fim')
    vendedor_filtro = request.GET.get('vendedor') # Para o Gerente filtrar

    if data_ini and data_fim:
        itens = itens.filter(venda__data_venda__date__range=[data_ini, data_fim])
    
    if request.user.cargo != 'VENDEDOR' and vendedor_filtro:
        itens = itens.filter(venda__vendedor_id=vendedor_filtro)

    # 4. Totais
    total_comissao = sum(i.comissao_valor for i in itens)
    total_vendido = sum(i.subtotal for i in itens)

    # Lista de vendedores para o filtro do Gerente
    vendedores = Usuario.objects.filter(empresa=request.user.empresa)

    return render(request, 'core/minhas_comissoes.html', {
        'itens': itens,
        'total_comissao': total_comissao,
        'total_vendido': total_vendido,
        'vendedores': vendedores,
        'data_ini': data_ini,
        'data_fim': data_fim
    })

# =========================================================
#  GESTÃO DE CADASTROS (CLIENTES, FORNECEDORES, CATEGORIAS)
# =========================================================

# --- CLIENTES ---
@login_required
def lista_clientes(request):
    clientes = Cliente.objects.filter(empresa=request.user.empresa).order_by('-data_ultima_compra')
    
    hoje = timezone.now()
    
    # Vamos processar a lista para adicionar o status visual
    for c in clientes:
        if c.data_ultima_compra:
            dias_sem_comprar = (hoje - c.data_ultima_compra).days
            c.dias_sem_comprar = dias_sem_comprar
            if dias_sem_comprar > 30:
                c.status_compra = 'INATIVO' # Vermelho
            else:
                c.status_compra = 'ATIVO'   # Verde
        else:
            c.status_compra = 'NOVO'        # Azul (Nunca comprou)
            c.dias_sem_comprar = -1

    return render(request, 'core/lista_clientes.html', {'clientes': clientes})

@login_required
def adicionar_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.empresa = request.user.empresa
            obj.save()
            return redirect('lista_clientes')
    else:
        form = ClienteForm()
    return render(request, 'core/form_generico.html', {'form': form, 'titulo': 'Novo Cliente'})

@login_required
def editar_cliente(request, id):
    obj = get_object_or_404(Cliente, id=id, empresa=request.user.empresa)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect('lista_clientes')
    else:
        form = ClienteForm(instance=obj)
    return render(request, 'core/form_generico.html', {'form': form, 'titulo': 'Editar Cliente'})

# --- FORNECEDORES ---
@login_required
def lista_fornecedores(request):
    fornecedores = Fornecedor.objects.filter(empresa=request.user.empresa)
    return render(request, 'core/lista_fornecedores.html', {'fornecedores': fornecedores})

@login_required
def adicionar_fornecedor(request):
    if request.method == 'POST':
        form = FornecedorForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.empresa = request.user.empresa
            obj.save()
            return redirect('lista_fornecedores')
    else:
        form = FornecedorForm()
    return render(request, 'core/form_generico.html', {'form': form, 'titulo': 'Novo Fornecedor'})

# --- CATEGORIAS ---
@login_required
def lista_categorias(request):
    categorias = Categoria.objects.filter(empresa=request.user.empresa)
    return render(request, 'core/lista_categorias.html', {'categorias': categorias})

@login_required
def adicionar_categoria(request):
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.empresa = request.user.empresa
            obj.save()
            return redirect('lista_categorias')
    else:
        form = CategoriaForm()
    return render(request, 'core/form_generico.html', {'form': form, 'titulo': 'Nova Categoria'})

# =========================================================
#  CENTRAL DE RELATÓRIOS
# =========================================================
@login_required
def relatorios(request):
    # Bloqueio para vendedor
    if request.user.cargo == 'VENDEDOR':
        return HttpResponseForbidden("Acesso Negado")

    # Filtros de Data (Padrão: Mês atual)
    hoje = timezone.now().date()
    inicio_mes = hoje.replace(day=1)
    
    data_ini = request.GET.get('data_ini', inicio_mes.strftime('%Y-%m-%d'))
    data_fim = request.GET.get('data_fim', hoje.strftime('%Y-%m-%d'))
    tipo_relatorio = request.GET.get('tipo', 'vendas') # Padrão: vendas

    contexto = {
        'data_ini': data_ini,
        'data_fim': data_fim,
        'tipo': tipo_relatorio,
    }

    # --- 1. RELATÓRIO DE VENDAS ---
    if tipo_relatorio == 'vendas':
        vendas = Venda.objects.filter(
            empresa=request.user.empresa,
            status='FECHADA',
            data_venda__date__range=[data_ini, data_fim]
        )
        
        # Agrupamento por Forma de Pagamento
        por_pagamento = vendas.values('forma_pagamento__nome').annotate(
            total=Sum('valor_total'),
            qtd=Count('id')
        )
        
        contexto.update({
            'vendas': vendas,
            'total_periodo': vendas.aggregate(Sum('valor_total'))['valor_total__sum'] or 0,
            'qtd_vendas': vendas.count(),
            'por_pagamento': por_pagamento
        })

    # --- 2. RELATÓRIO FINANCEIRO (DRE) ---
    elif tipo_relatorio == 'financeiro':
        lancamentos = Lancamento.objects.filter(
            empresa=request.user.empresa,
            data_pagamento__range=[data_ini, data_fim],
            pago=True
        )
        
        receitas = lancamentos.filter(tipo='RECEITA')
        despesas = lancamentos.filter(tipo='DESPESA')
        
        total_receitas = receitas.aggregate(Sum('valor'))['valor__sum'] or 0
        total_despesas = despesas.aggregate(Sum('valor'))['valor__sum'] or 0
        lucro = total_receitas - total_despesas
        
        contexto.update({
            'lancamentos': lancamentos,
            'total_receitas': total_receitas,
            'total_despesas': total_despesas,
            'lucro': lucro,
            'margem': (lucro / total_receitas * 100) if total_receitas > 0 else 0
        })

    # --- 3. RELATÓRIO DE PRODUTOS (Ranking) ---
    elif tipo_relatorio == 'produtos':
        itens = ItemVenda.objects.filter(
            venda__empresa=request.user.empresa,
            venda__status='FECHADA',
            venda__data_venda__date__range=[data_ini, data_fim]
        ).values('produto__nome', 'produto__estoque_atual').annotate(
            qtd_vendida=Sum('quantidade'),
            # CORREÇÃO APLICADA AQUI (USANDO F):
            total_vendido=Sum(F('quantidade') * F('preco_unitario'))
        ).order_by('-qtd_vendida')
        
        contexto['ranking_produtos'] = itens

    # --- A LINHA QUE FALTAVA ---
    return render(request, 'core/relatorios.html', contexto)

@login_required
def configuracoes(request):
    # Só Gerente/Dono pode mexer aqui
    if request.user.cargo == 'VENDEDOR':
        return HttpResponseForbidden("Acesso Negado")

    empresa = request.user.empresa
    
    if request.method == 'POST':
        form = ConfiguracaoEmpresaForm(request.POST, request.FILES, instance=empresa)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ConfiguracaoEmpresaForm(instance=empresa)
    
    return render(request, 'core/configuracoes.html', {'form': form})

@login_required
def painel_estoque(request):
    produtos = Produto.objects.filter(empresa=request.user.empresa)
    
    # 1. Produtos com Estoque Baixo
    baixo_estoque = produtos.filter(estoque_atual__lte=F('estoque_minimo'))
    
    # 2. Valor Total em Estoque (Custo vs Venda)
    total_custo = sum(p.estoque_atual * p.preco_custo for p in produtos)
    total_venda = sum(p.estoque_atual * p.preco_venda for p in produtos)
    lucro_potencial = total_venda - total_custo

    # 3. Previsão de Término (Lógica Simples: Baseado na média de vendas geral ou estática)
    # Para algo robusto real, precisaríamos pegar vendas dos últimos 30 dias de cada produto.
    # Vamos fazer uma lista inteligente aqui:
    
    lista_inteligente = []
    hoje = timezone.now().date()
    inicio_mes = hoje - timezone.timedelta(days=30)
    
    for p in produtos:
        # Quantos vendeu nos últimos 30 dias?
        qtd_vendida = ItemVenda.objects.filter(
            produto=p, 
            venda__status='FECHADA',
            venda__data_venda__date__gte=inicio_mes
        ).aggregate(Sum('quantidade'))['quantidade__sum'] or 0
        
        # Cálculo de dias restantes
        if qtd_vendida > 0:
            media_diaria = qtd_vendida / 30
            dias_restantes = int(p.estoque_atual / media_diaria)
        else:
            dias_restantes = 999 # "Infinito" (sem vendas)
            
        status = "Ok"
        if dias_restantes < 7: status = "Crítico (Acaba em 1 semana)"
        elif dias_restantes < 15: status = "Atenção (Acaba em 2 semanas)"
        
        lista_inteligente.append({
            'nome': p.nome,
            'atual': p.estoque_atual,
            'vendidos_30d': qtd_vendida,
            'dias_restantes': dias_restantes,
            'status': status
        })
    
    # Ordena pelos que vão acabar mais rápido
    lista_inteligente.sort(key=lambda x: x['dias_restantes'])

    return render(request, 'core/painel_estoque.html', {
        'baixo_estoque': baixo_estoque,
        'total_custo': total_custo,
        'total_venda': total_venda,
        'lucro_potencial': lucro_potencial,
        'lista_inteligente': lista_inteligente[:10], # Top 10 críticos
        'total_produtos': produtos.count()
    })
    # =========================================================
#  GESTÃO DE EQUIPE
# =========================================================
@login_required
def lista_equipe(request):
    # Segurança: Vendedor não vê isso
    if request.user.cargo == 'VENDEDOR':
        return HttpResponseForbidden("Acesso Negado")
        
    # Lista apenas usuários da MESMA empresa
    usuarios = Usuario.objects.filter(empresa=request.user.empresa)
    return render(request, 'core/lista_equipe.html', {'usuarios': usuarios})

@login_required
def adicionar_colaborador(request):
    if request.user.cargo == 'VENDEDOR': return HttpResponseForbidden()

    if request.method == 'POST':
        form = UsuarioForm(request.POST)
        if form.is_valid():
            novo_user = form.save(commit=False)
            novo_user.empresa = request.user.empresa # Vincula à loja atual
            
            # Define a senha corretamente (Criptografa)
            senha_texto = form.cleaned_data.get('senha')
            if senha_texto:
                novo_user.set_password(senha_texto)
            else:
                novo_user.set_password('123456') # Senha padrão se não informar
                
            novo_user.save()
            return redirect('lista_equipe')
    else:
        form = UsuarioForm()
        
    return render(request, 'core/form_generico.html', {'form': form, 'titulo': 'Novo Colaborador'})

@login_required
def editar_colaborador(request, user_id):
    if request.user.cargo == 'VENDEDOR': return HttpResponseForbidden()

    # Busca usuário garantindo que é da mesma empresa
    colaborador = get_object_or_404(Usuario, id=user_id, empresa=request.user.empresa)
    
    if request.method == 'POST':
        form = UsuarioForm(request.POST, instance=colaborador)
        if form.is_valid():
            user_editado = form.save(commit=False)
            
            # Se preencheu senha nova, troca. Se não, mantém a antiga.
            senha_nova = form.cleaned_data.get('senha')
            if senha_nova:
                user_editado.set_password(senha_nova)
                
            user_editado.save()
            return redirect('lista_equipe')
    else:
        form = UsuarioForm(instance=colaborador)
        
    return render(request, 'core/form_generico.html', {'form': form, 'titulo': 'Editar Colaborador'})

@login_required
def excluir_colaborador(request, user_id):
    if request.user.cargo == 'VENDEDOR': return HttpResponseForbidden()
    
    colaborador = get_object_or_404(Usuario, id=user_id, empresa=request.user.empresa)
    
    # Impede que o usuário se exclua
    if colaborador.id == request.user.id:
        return HttpResponseForbidden("Você não pode excluir a si mesmo.")
        
    colaborador.delete()
    return redirect('lista_equipe')