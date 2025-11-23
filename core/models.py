from django.db import models
from django.contrib.auth.models import AbstractUser
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from django.utils import timezone

# =========================================================
#  1. EMPRESAS E USUÁRIOS
# =========================================================
class Empresa(models.Model):
    # --- 1. PLANOS E ASSINATURA ---
    PLANOS_CHOICES = (
        ('ESSENCIAL', 'Essencial (R$ 129)'),
        ('PRO', 'Profissional (R$ 249)'),
        ('EXPANSAO', 'Expansão (Corporativo)'),
    )
    plano = models.CharField(max_length=20, choices=PLANOS_CHOICES, default='ESSENCIAL')
    valor_mensalidade = models.DecimalField(max_digits=10, decimal_places=2, default=99.90)
    data_vencimento = models.DateField(null=True, blank=True)
    ativa = models.BooleanField(default=True)
    # Integração Asaas
    asaas_customer_id = models.CharField(max_length=100, blank=True, null=True)

    @property
    def dias_restantes(self):
        if not self.data_vencimento:
            return 0
        hoje = timezone.now().date()
        delta = self.data_vencimento - hoje
        return delta.days

    # --- 2. DADOS BÁSICOS ---
    nome_fantasia = models.CharField(max_length=255)
    razao_social = models.CharField(max_length=255, blank=True, null=True)
    cnpj = models.CharField(max_length=18, unique=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    
    # --- 3. PERSONALIZAÇÃO (LOGO E CORES) ---
    logo = models.ImageField(upload_to='logos_empresas/', null=True, blank=True)
    mensagem_cupom = models.CharField(max_length=200, default="Obrigado pela preferência!", blank=True)
    cor_sistema = models.CharField(max_length=20, default="#0d6efd", help_text="Cor principal do sistema (Hex)")
    
    # --- 4. DADOS FISCAIS ---
    ambiente_fiscal = models.CharField(max_length=20, default='HOMOLOGACAO', choices=(('HOMOLOGACAO', 'Teste'), ('PRODUCAO', 'Valendo')))
    token_api_fiscal = models.CharField(max_length=200, blank=True, null=True)
    csc_token = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.nome_fantasia

    # --- LÓGICA DE LIMITES ---
    def limite_usuarios(self):
        if self.plano == 'ESSENCIAL': return 4
        if self.plano == 'PRO': return 10
        return 999 # Expansão ilimitado

    def tem_acesso_financeiro(self):
        # Essencial Não tem financeiro completo, só Pro e Expansão
        return self.plano in ['PRO', 'EXPANSAO']    # Campos de Personalização (Logo e Fiscal)
    
    logo = models.ImageField(upload_to='logos_empresas/', null=True, blank=True)
    mensagem_cupom = models.CharField(max_length=200, default="Obrigado pela preferência!", blank=True)
    cor_sistema = models.CharField(max_length=20, default="#0d6efd", help_text="Cor principal do sistema (Hex)")
    
    # Dados Fiscais (Para o futuro)
    ambiente_fiscal = models.CharField(max_length=20, default='HOMOLOGACAO', choices=(('HOMOLOGACAO', 'Teste'), ('PRODUCAO', 'Valendo')))
    token_api_fiscal = models.CharField(max_length=200, blank=True, null=True)
    csc_token = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.nome_fantasia

class Usuario(AbstractUser):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, null=True, blank=True, related_name='usuarios')
    
    TIPO_CHOICES = (
        ('VENDEDOR', 'Vendedor'),
        ('GERENTE', 'Gerente'),
        ('CAIXA', 'Operador de Caixa'),
        ('ESTOQUISTA', 'Estoquista'),
        ('SUPORTE', 'Suporte do Sistema'),
    )
    cargo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='VENDEDOR')

    def __str__(self):
        return f"{self.username} ({self.get_cargo_display()})"

# =========================================================
#  2. CLASSE ABSTRATA
# =========================================================
class ModeloDoTenant(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    ativo = models.BooleanField(default=True)
    class Meta:
        abstract = True

# =========================================================
#  3. CADASTROS BÁSICOS
# =========================================================
class Fornecedor(ModeloDoTenant):
    razao_social = models.CharField(max_length=200)
    cnpj = models.CharField(max_length=20, blank=True, null=True)
    telefone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    
    def __str__(self):
        return self.razao_social

class Categoria(ModeloDoTenant):
    nome = models.CharField(max_length=100)
    def __str__(self):
        return self.nome

class FormaPagamento(ModeloDoTenant):
    nome = models.CharField(max_length=50)
    taxa = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    dias_para_receber = models.IntegerField(default=0)
    
    def __str__(self):
        return self.nome

# =========================================================
#  4. CAIXA E MOVIMENTO
# =========================================================
class Caixa(ModeloDoTenant):
    nome = models.CharField(max_length=50, default="Caixa 01")
    observacao = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.nome} - {self.empresa.nome_fantasia}"

class MovimentoCaixa(ModeloDoTenant):
    caixa = models.ForeignKey(Caixa, on_delete=models.PROTECT)
    operador = models.ForeignKey(Usuario, on_delete=models.PROTECT)
    
    data_abertura = models.DateTimeField(auto_now_add=True)
    data_fechamento = models.DateTimeField(null=True, blank=True)
    
    valor_abertura = models.DecimalField(max_digits=10, decimal_places=2)
    valor_fechamento = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    diferenca = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    observacao_fechamento = models.TextField(blank=True, null=True)
    
    status = models.CharField(max_length=20, default='ABERTO', choices=(('ABERTO', 'Aberto'), ('FECHADO', 'Fechado')))

    def __str__(self):
        return f"Turno #{self.id} - {self.operador.username}"

# =========================================================
#  5. PRODUTOS E CLIENTES
# =========================================================
class Produto(ModeloDoTenant):
    nome = models.CharField(max_length=200)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True)
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.SET_NULL, null=True, blank=True)
    codigo_barras = models.CharField(max_length=50, blank=True, null=True)
    
    preco_custo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    preco_venda = models.DecimalField(max_digits=10, decimal_places=2)
    porcentagem_comissao = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    estoque_atual = models.IntegerField(default=0)
    estoque_minimo = models.IntegerField(default=5)
    
    descricao = models.TextField(blank=True, null=True)
    foto = models.ImageField(upload_to='produtos/', blank=True, null=True)
    qrcode_img = models.ImageField(upload_to='qrcodes/', blank=True, null=True)

    def __str__(self):
        return self.nome
    
    def save(self, *args, **kwargs):
        if not self.qrcode_img:
            conteudo_qr = f"ID:{self.id}|{self.nome}|R$ {self.preco_venda}"
            qr = qrcode.QRCode(version=1, box_size=10, border=2)
            qr.add_data(conteudo_qr)
            qr.make(fit=True)
            img = qr.make_image(fill='black', back_color='white')
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            self.qrcode_img.save(f'qr_{self.id}.png', ContentFile(buffer.getvalue()), save=False)
        super().save(*args, **kwargs)

class Cliente(ModeloDoTenant):
    nome = models.CharField(max_length=200)
    cpf_cnpj = models.CharField(max_length=20, blank=True, null=True)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    endereco = models.CharField(max_length=255, blank=True, null=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)
    data_ultima_compra = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.nome

# =========================================================
#  6. VENDAS
# =========================================================
class Venda(ModeloDoTenant):
    STATUS_CHOICES = (
        ('ORCAMENTO', 'Orçamento'),
        ('FECHADA', 'Venda Fechada'),
        ('CANCELADA', 'Cancelada'),
    )
    forma_pagamento = models.ForeignKey(FormaPagamento, on_delete=models.PROTECT, null=True, blank=True)
    vendedor = models.ForeignKey(Usuario, on_delete=models.PROTECT)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, null=True, blank=True)
    movimento_caixa = models.ForeignKey(MovimentoCaixa, on_delete=models.PROTECT, null=True, blank=True, related_name='vendas')
    
    data_venda = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ORCAMENTO')
    
    desconto = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    nota_fiscal_url = models.URLField(blank=True, null=True)
    nota_fiscal_emitida = models.BooleanField(default=False)

    def __str__(self):
        return f"Venda #{self.id}"

class ItemVenda(models.Model):
    venda = models.ForeignKey(Venda, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT)
    quantidade = models.IntegerField(default=1)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    comissao_valor = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def save(self, *args, **kwargs):
        if not self.preco_unitario:
            self.preco_unitario = self.produto.preco_venda
        
        porcentagem = self.produto.porcentagem_comissao or 0
        self.comissao_valor = (self.preco_unitario * self.quantidade) * (porcentagem / 100)
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return self.quantidade * self.preco_unitario

# =========================================================
#  7. FINANCEIRO
# =========================================================
class Lancamento(ModeloDoTenant):
    TIPO_CHOICES = (
        ('RECEITA', 'Receita'),
        ('DESPESA', 'Despesa'),
    )
    titulo = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    data_vencimento = models.DateField()
    data_pagamento = models.DateField(null=True, blank=True)
    pago = models.BooleanField(default=False)
    venda_origem = models.ForeignKey(Venda, on_delete=models.SET_NULL, null=True, blank=True, related_name='lancamentos')
    
    def __str__(self):
        return f"{self.titulo} - {self.valor}"
    
    class Meta:
        ordering = ['data_vencimento']