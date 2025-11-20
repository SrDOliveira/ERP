from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Empresa, Usuario, Categoria, Produto, Cliente, 
    Venda, ItemVenda, Lancamento, Fornecedor, 
    FormaPagamento, Caixa, MovimentoCaixa
)

# 1. Usuário (Com o novo cargo visível)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Informações SaaS', {'fields': ('empresa', 'cargo')}),
    )
    list_display = ('username', 'email', 'empresa', 'cargo', 'is_staff')

# 2. Configurações Básicas (Fornecedor, Pagamento, Caixa)
class FornecedorAdmin(admin.ModelAdmin):
    list_display = ('razao_social', 'empresa', 'telefone', 'email')
    list_filter = ('empresa',)

class FormaPagamentoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'empresa', 'taxa', 'dias_para_receber')

class CaixaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'empresa', 'observacao')

class MovimentoCaixaAdmin(admin.ModelAdmin):
    list_display = ('id', 'caixa', 'operador', 'data_abertura', 'status', 'valor_abertura')
    list_filter = ('status', 'data_abertura', 'empresa')

# 3. Produto (Atualizado com Fornecedor e QR Code)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'empresa', 'preco_venda', 'estoque_atual', 'fornecedor', 'porcentagem_comissao')
    list_filter = ('empresa', 'categoria', 'fornecedor')
    search_fields = ('nome', 'codigo_barras')

# 4. Venda e Itens
class ItemVendaInline(admin.TabularInline):
    model = ItemVenda
    extra = 0
    readonly_fields = ('subtotal', 'comissao_valor') # Mostra a comissão calculada

class VendaAdmin(admin.ModelAdmin):
    inlines = [ItemVendaInline]
    list_display = ('id', 'empresa', 'cliente', 'status', 'valor_total', 'forma_pagamento', 'data_venda')
    list_filter = ('empresa', 'status', 'data_venda', 'forma_pagamento')
    
    # Função para criar o botão de PDF no admin
    from django.utils.html import format_html
    from django.urls import reverse
    def botao_imprimir(self, obj):
        if obj.id:
            # Link genérico, ajustaremos depois se precisar
            return "Salvo"
        return "-"

# --- REGISTRO DAS TABELAS ---
admin.site.register(Empresa)
admin.site.register(Usuario, UsuarioAdmin)
admin.site.register(Categoria)
admin.site.register(Cliente)
admin.site.register(Lancamento)

# As Novas Tabelas ERP
admin.site.register(Fornecedor, FornecedorAdmin)
admin.site.register(FormaPagamento, FormaPagamentoAdmin)
admin.site.register(Caixa, CaixaAdmin)
admin.site.register(MovimentoCaixa, MovimentoCaixaAdmin)
admin.site.register(Produto, ProdutoAdmin)
admin.site.register(Venda, VendaAdmin)