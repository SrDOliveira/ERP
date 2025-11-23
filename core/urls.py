from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('nova-venda/', views.criar_venda, name='criar_venda'),  # <--- O erro diz que esta linha não existe
    path('pdv/<int:venda_id>/', views.pdv, name='pdv'),
    path('pdv/<int:venda_id>/adicionar/', views.adicionar_item, name='adicionar_item'),
    path('orcamento/<int:venda_id>/', views.gerar_orcamento_pdf, name='gerar_orcamento_pdf'),
    path('financeiro/', views.financeiro, name='financeiro'),
    path('financeiro/nova-despesa/', views.adicionar_despesa, name='adicionar_despesa'),
    path('saas-admin/', views.saas_painel, name='saas_painel'),
    path('saas-admin/bloquear/<int:empresa_id>/', views.alternar_status_loja, name='alternar_status_loja'),
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('produtos/', views.lista_produtos, name='lista_produtos'),
    path('produtos/novo/', views.adicionar_produto, name='adicionar_produto'),
    path('produtos/editar/<int:produto_id>/', views.editar_produto, name='editar_produto'),
    path('produtos/excluir/<int:produto_id>/', views.excluir_produto, name='excluir_produto'),
    path('produtos/catalogo-qr/', views.catalogo_qr, name='catalogo_qr'),
    path('venda/cupom/<int:venda_id>/', views.imprimir_cupom, name='imprimir_cupom'),
    path('saas-admin/contrato/<int:empresa_id>/', views.gerar_contrato_pdf, name='gerar_contrato_pdf'),
    path('caixa/', views.gerenciar_caixa, name='gerenciar_caixa'),
    path('caixa/abrir/', views.abrir_caixa, name='abrir_caixa'),
    path('caixa/fechar/<int:movimento_id>/', views.fechar_caixa, name='fechar_caixa'),
    path('comissoes/', views.minhas_comissoes, name='minhas_comissoes'),
    # Clientes
    path('clientes/', views.lista_clientes, name='lista_clientes'),
    path('clientes/novo/', views.adicionar_cliente, name='adicionar_cliente'),
    path('clientes/editar/<int:id>/', views.editar_cliente, name='editar_cliente'),
    
    # Fornecedores
    path('fornecedores/', views.lista_fornecedores, name='lista_fornecedores'),
    path('fornecedores/novo/', views.adicionar_fornecedor, name='adicionar_fornecedor'),
    
    # Categorias
    path('categorias/', views.lista_categorias, name='lista_categorias'),
    path('categorias/novo/', views.adicionar_categoria, name='adicionar_categoria'),

    path('relatorios/', views.relatorios, name='relatorios'),

    path('configuracoes/', views.configuracoes, name='configuracoes'),

    path('estoque/painel/', views.painel_estoque, name='painel_estoque'),

    # Equipe
    path('equipe/', views.lista_equipe, name='lista_equipe'),
    path('equipe/novo/', views.adicionar_colaborador, name='adicionar_colaborador'),
    path('equipe/editar/<int:user_id>/', views.editar_colaborador, name='editar_colaborador'),
    path('equipe/excluir/<int:user_id>/', views.excluir_colaborador, name='excluir_colaborador'),
    path('cadastro/', views.cadastro_loja, name='cadastro_loja'),
    path('pagamento/iniciar/<str:plano>/', views.iniciar_pagamento, name='iniciar_pagamento'),
    path('webhook/asaas/', views.webhook_asaas, name='webhook_asaas'),
    path('assinatura/planos/', views.escolher_plano, name='escolher_plano'),

]