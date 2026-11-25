import 'package:app/core/theme/cores.dart';
import 'package:app/features/sobre/presentation/versao_app.dart';
import 'package:app/shared/widgets/ilustracao_vetfarmaco.dart';
import 'package:flutter/material.dart';

/// `/sobre` — de onde vêm as respostas, o que o app é e quais são seus
/// limites (`docs/FRONTEND_SPEC.md` §22).
///
/// Só leitura e sem rede: fora do fluxo de consulta medido.
class SobrePage extends StatelessWidget {
  /// Cria a tela.
  const new({super.key});

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Sobre o aplicativo')),
      body: SafeArea(
        child: SingleChildScrollView(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 560),
              child: Column(
                children: [
                  const IlustracaoVetFarmaco(
                    cena: Cena.sobreFaixa,
                    largura: double.infinity,
                  ),
                  Padding(
                    padding: const EdgeInsets.all(24),
                    child: _Secoes(tema: tema),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// As seções de texto da tela Sobre.
class _Secoes extends StatelessWidget {
  const new({required this.tema});

  final TextTheme tema;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _Secao(
          titulo: 'De onde vêm as respostas',
          filhos: [
            Text(
              'As respostas são montadas só a partir de trechos '
              'recuperados de Spinosa et al. (2017) e de seis '
              'bulas: carprofeno, fenobarbital, insulina NPH, '
              'ivermectina, meloxicam e tramadol. Cada afirmação '
              'traz o número da citação; tocar nele abre o trecho '
              'original, com a fonte.',
              style: tema.bodyLarge,
            ),
          ],
        ),
        _Secao(
          titulo: 'Ferramenta de apoio',
          filhos: [
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                border: Border(
                  left: BorderSide(color: context.cores.iodo, width: 3),
                ),
                color: context.cores.iodo.withValues(alpha: 0.12),
              ),
              child: Text(
                'Este aplicativo é uma prova de conceito '
                'acadêmica e uma ferramenta de apoio. Ele não '
                'emite prescrição e não substitui o julgamento '
                'clínico do médico veterinário responsável.',
                style: tema.bodyLarge,
              ),
            ),
          ],
        ),
        _Secao(
          titulo: 'Privacidade',
          filhos: [
            Text(
              'Identificações de tutor e animal são removidas no '
              'próprio aparelho antes do envio. O app não tem '
              'login nem cadastro e não coleta dados pessoais.',
              style: tema.bodyLarge,
            ),
            const SizedBox(height: 8),
            Text(
              'Essa remoção não reconhece nomes próprios em texto '
              'livre de forma confiável. Por isso, não inclua '
              'nomes de tutores, de animais ou números de '
              'prontuário na pergunta.',
              style: tema.bodyLarge,
            ),
          ],
        ),
        const _Secao(
          titulo: 'Limites do sistema',
          filhos: [
            _Item(
              'O acervo é pequeno: sete documentos, o livro de '
              'Spinosa et al. (2017) e seis bulas.',
            ),
            _Item(
              'Parte das bulas é de uso humano ou de outra espécie; '
              'nem sempre dá para atribuir uma dose à espécie '
              'perguntada.',
            ),
            _Item(
              'Quando o acervo não sustenta a resposta, o sistema '
              'diz «Sem evidência suficiente no acervo.» em vez de '
              'responder.',
            ),
            _Item(
              'Respostas com confiança baixa pedem conferência da '
              'fonte antes de qualquer conduta.',
            ),
            _Item(
              'Cada consulta é independente: o sistema não guarda '
              'a conversa.',
            ),
            _Item(
              'Uma consulta nova precisa de conexão; as respostas '
              'salvas podem ser relidas sem rede.',
            ),
          ],
        ),
        _Secao(
          titulo: 'Versões',
          filhos: [
            Text('Aplicativo: $versaoApp', style: tema.bodyLarge),
            const SizedBox(height: 4),
            Text(
              'O modelo, a data e o índice de cada resposta '
              'aparecem no rodapé dela.',
              style: tema.bodyLarge,
            ),
          ],
        ),
      ],
    );
  }
}

class _Secao extends StatelessWidget {
  const new({required this.titulo, required this.filhos});

  final String titulo;
  final List<Widget> filhos;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 24),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Semantics(
          header: true,
          child: Text(titulo, style: Theme.of(context).textTheme.titleLarge),
        ),
        const SizedBox(height: 8),
        ...filhos,
      ],
    ),
  );
}

class _Item extends StatelessWidget {
  const new(this.texto);

  final String texto;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(padding: EdgeInsets.only(right: 8), child: Text('•')),
        Expanded(
          child: Text(texto, style: Theme.of(context).textTheme.bodyLarge),
        ),
      ],
    ),
  );
}
