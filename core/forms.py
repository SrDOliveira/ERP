from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from .models import (
    Produto, MovimentoCaixa, Usuario, Caixa, Empresa, 
    Categoria, Fornecedor, Cliente, Chamado, AjusteEstoque
)

# --- SUPORTE ---
class ChamadoForm(forms.ModelForm):
    class Meta:
        model = Chamado
        fields = ['tipo', 'assunto', 'mensagem', 'anexo']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'assunto': forms.TextInput(attrs={'class': 'form-control'}),
            'mensagem': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'anexo': forms.FileInput(attrs={'class': 'form-control'}),
        }

# --- ESTOQUE ---
class AjusteEstoqueForm(forms.ModelForm):
    class Meta:
        model = AjusteEstoque
        fields = ['produto', 'quantidade', 'motivo', 'observacao']
        widgets = {
            'produto': forms.Select(attrs={'class': 'form-select'}),
            'quantidade': forms.NumberInput(attrs={'class': 'form-control'}),
            'motivo': forms.Select(attrs={'class': 'form-select'}),
            'observacao': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['produto'].queryset = Produto.objects.filter(empresa=user.empresa)

# --- PRODUTO ---

class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        # ESTA LINHA ABAIXO É A QUE ESTAVA FALTANDO OU COM ERRO:
        fields = ['nome', 'tamanho', 'cor', 'categoria', 'fornecedor', 'preco_custo', 'preco_venda', 'porcentagem_comissao', 'estoque_atual', 'codigo_barras', 'descricao', 'foto']
        
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'tamanho': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: P, M, 38'}),
            'cor': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Azul Marinho'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'fornecedor': forms.Select(attrs={'class': 'form-select'}),
            'preco_custo': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'preco_venda': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'porcentagem_comissao': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'estoque_atual': forms.NumberInput(attrs={'class': 'form-control'}),
            'codigo_barras': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'foto': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super(ProdutoForm, self).__init__(*args, **kwargs)
        # Campos Opcionais
        self.fields['porcentagem_comissao'].required = False
        self.fields['fornecedor'].required = False
        self.fields['categoria'].required = False
        self.fields['codigo_barras'].required = False
        self.fields['tamanho'].required = False
        self.fields['cor'].required = False
        self.fields['foto'].required = False
        
# --- CAIXA ---
class AberturaCaixaForm(forms.ModelForm):
    class Meta:
        model = MovimentoCaixa
        fields = ['caixa', 'valor_abertura']
        widgets = {
            'caixa': forms.Select(attrs={'class': 'form-select form-select-lg'}),
            'valor_abertura': forms.NumberInput(attrs={'class': 'form-control form-select-lg', 'step': '0.01'}),
        }
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['caixa'].queryset = Caixa.objects.filter(empresa=user.empresa)

class FechamentoCaixaForm(forms.ModelForm):
    gerente = forms.ModelChoiceField(
        queryset=Usuario.objects.none(), 
        label="Autorização do Gerente", 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    senha_gerente = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}), 
        label="Senha do Gerente"
    )

    class Meta:
        model = MovimentoCaixa
        fields = ['valor_fechamento', 'observacao_fechamento']
        widgets = {
            'valor_fechamento': forms.NumberInput(attrs={'class': 'form-control form-control-lg', 'step': '0.01'}),
            'observacao_fechamento': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['gerente'].queryset = Usuario.objects.filter(
            empresa=user.empresa, 
            cargo__in=['GERENTE', 'SUPORTE']
        )

    def clean(self):
        cleaned_data = super().clean()
        gerente = cleaned_data.get('gerente')
        senha = cleaned_data.get('senha_gerente')

        if gerente and senha:
            if not gerente.check_password(senha):
                raise ValidationError("Senha do gerente incorreta!")
        return cleaned_data

# --- CADASTROS GERAIS ---
class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nome']
        widgets = {'nome': forms.TextInput(attrs={'class': 'form-control'})}

class FornecedorForm(forms.ModelForm):
    class Meta:
        model = Fornecedor
        fields = ['razao_social', 'cnpj', 'telefone', 'email']
        widgets = {
            'razao_social': forms.TextInput(attrs={'class': 'form-control'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nome', 'cpf_cnpj', 'telefone', 'email', 'endereco']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'cpf_cnpj': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'endereco': forms.TextInput(attrs={'class': 'form-control'}),
        }
    

class ConfiguracaoEmpresaForm(forms.ModelForm):
    class Meta:
        model = Empresa
        fields = ['nome_fantasia', 'cnpj', 'logo', 'mensagem_cupom', 'cor_sistema']
        widgets = {
            'nome_fantasia': forms.TextInput(attrs={'class': 'form-control'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control'}),
            'mensagem_cupom': forms.TextInput(attrs={'class': 'form-control'}),
            'cor_sistema': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

class UsuarioForm(forms.ModelForm):
    senha = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=False, help_text="Deixe em branco para manter a atual")
    
    class Meta:
        model = Usuario
        fields = ['username', 'first_name', 'last_name', 'email', 'cargo']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'cargo': forms.Select(attrs={'class': 'form-select'}),
        }

# --- CADASTRO PÚBLICO (SIGN UP) ---
class CadastroLojaForm(forms.Form):
    nome_loja = forms.CharField(label="Nome da Loja", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Boutique da Ana'}))
    
    # Campo de Ramo (Wizard)
    ramo = forms.ChoiceField(
        label="Qual seu segmento?",
        choices=Empresa.RAMO_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Dados do Dono
    nome_usuario = forms.CharField(label="Seu Nome", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Seu nome completo'}))
    email = forms.EmailField(label="E-mail", widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'seu@email.com'}))
    username = forms.CharField(label="Usuário para Login", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: ana_boutique'}))
    senha = forms.CharField(label="Senha", widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    
    def clean_username(self):
        username = self.cleaned_data['username']
        if Usuario.objects.filter(username=username).exists():
            raise ValidationError("Este nome de usuário já existe. Escolha outro.")
        return username