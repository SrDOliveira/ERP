from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from .models import Produto, MovimentoCaixa, Usuario, Caixa, Empresa, Categoria, Fornecedor, Cliente

# ... (aqui começam as classes ProdutoForm, etc)

# --- Formulário de Produto ---
class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        # Atualizei para incluir os novos campos: Fornecedor e Comissão
        fields = ['nome', 'categoria', 'fornecedor', 'preco_custo', 'preco_venda', 'porcentagem_comissao', 'estoque_atual', 'codigo_barras', 'descricao', 'foto']
        
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'fornecedor': forms.Select(attrs={'class': 'form-select'}), # Novo campo
            'preco_custo': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'preco_venda': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'porcentagem_comissao': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}), # Novo campo
            'estoque_atual': forms.NumberInput(attrs={'class': 'form-control'}),
            'codigo_barras': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'foto': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

# --- Formulário de Abertura de Caixa ---
class AberturaCaixaForm(forms.ModelForm):
    class Meta:
        model = MovimentoCaixa
        fields = ['caixa', 'valor_abertura']
        widgets = {
            'caixa': forms.Select(attrs={'class': 'form-select form-select-lg'}),
            'valor_abertura': forms.NumberInput(attrs={'class': 'form-control form-control-lg', 'step': '0.01'}),
        }
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtra apenas caixas da empresa do usuário
        self.fields['caixa'].queryset = Caixa.objects.filter(empresa=user.empresa)

# --- Formulário de Fechamento de Caixa ---
class FechamentoCaixaForm(forms.ModelForm):
    # Campos extras para autenticação do gerente
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
        # Popula o campo gerente apenas com gerentes/donos daquela empresa
        self.fields['gerente'].queryset = Usuario.objects.filter(
            empresa=user.empresa, 
            cargo__in=['GERENTE', 'SUPORTE']
        )

    def clean(self):
        cleaned_data = super().clean()
        gerente = cleaned_data.get('gerente')
        senha = cleaned_data.get('senha_gerente')

        if gerente and senha:
            # Verifica se a senha do gerente está correta
            if not gerente.check_password(senha):
                raise ValidationError("Senha do gerente incorreta!")
        return cleaned_data
    
    # ... (mantenha os imports e forms existentes)

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
        # Esta linha é OBRIGATÓRIA e deve estar ativa:
        fields = ['nome_fantasia', 'cnpj', 'logo', 'mensagem_cupom', 'cor_sistema']
        
        widgets = {
            'nome_fantasia': forms.TextInput(attrs={'class': 'form-control'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control'}),
            'mensagem_cupom': forms.TextInput(attrs={'class': 'form-control'}),
            'cor_sistema': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

        # Adicione este import no topo se não tiver
from django.contrib.auth.models import User 

# ... (outros forms)

class UsuarioForm(forms.ModelForm):
    senha = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=False, help_text="Deixe em branco para manter a atual (na edição)")
    
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

# Adicione no final do arquivo core/forms.py

class CadastroLojaForm(forms.Form):
    # Dados da Loja
    nome_loja = forms.CharField(label="Nome da Loja", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Boutique da Ana'}))
    
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
    

# =========================================================
#  AUTO-CADASTRO (SIGN UP)
# =========================================================
def cadastro_loja(request):
    if request.method == 'POST':
        form = CadastroLojaForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            
            # 1. Criar a Empresa
            nova_empresa = Empresa.objects.create(
                nome_fantasia=data['nome_loja'],
                ativa=True
            )
            
            # 2. Criar o Usuário Dono (Gerente)
            novo_usuario = Usuario.objects.create_user(
                username=data['username'],
                email=data['email'],
                password=data['senha'],
                first_name=data['nome_usuario'],
                empresa=nova_empresa,
                cargo='GERENTE' # Já nasce mandando
            )
            
            # 3. ONBOARDING: Criar dados iniciais para a loja não ficar vazia
            Caixa.objects.create(empresa=nova_empresa, nome="Caixa Principal", observacao="Caixa padrão do sistema")
            FormaPagamento.objects.create(empresa=nova_empresa, nome="Dinheiro", taxa=0)
            FormaPagamento.objects.create(empresa=nova_empresa, nome="Cartão de Crédito", taxa=3.5, dias_para_receber=30)
            FormaPagamento.objects.create(empresa=nova_empresa, nome="PIX", taxa=0)
            
            # 4. Logar e Redirecionar
            login(request, novo_usuario)
            messages.success(request, f"Bem-vindo ao Nexum! Sua loja '{data['nome_loja']}' está pronta.")
            return redirect('dashboard')
            
    else:
        form = CadastroLojaForm()
        
    return render(request, 'core/signup.html', {'form': form})