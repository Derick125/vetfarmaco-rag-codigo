import 'package:app/core/theme/cores.dart';
import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:app/features/resposta/presentation/widgets/ancora_citacao.dart';
import 'package:flutter/material.dart';

/// Raio dos cartões do app (o mesmo do balão da pergunta e dos chips).
const raioCartao = 12.0;

/// Cor de destaque (barra, ícone) de um alerta de [severidade]: `contra` para
/// contraindicação e `iodo` para cautela (`docs/FRONTEND_SPEC.md` §2).
Color destaqueAlerta(CoresVetFarmaco c, SeveridadeAlerta severidade) =>
    severidade == SeveridadeAlerta.contraindicacao ? c.contra : c.iodo;

/// Fundo levemente tingido do cartão: o destaque a 10% sobre o fundo da tela,
/// sem vermelho puro nem cor sólida.
Color fundoAlerta(CoresVetFarmaco c, SeveridadeAlerta severidade) =>
    Color.alphaBlend(
      destaqueAlerta(c, severidade).withValues(alpha: 0.10),
      c.paper,
    );

/// Palavra da severidade, em caixa normal (a severidade nunca vai só em cor).
String palavraSeveridade(SeveridadeAlerta severidade) =>
    severidade == SeveridadeAlerta.contraindicacao
    ? 'Contraindicação'
    : 'Cautela';

/// Ícone contornado da severidade: círculo com exclamação para
/// contraindicação, triângulo de aviso para cautela.
IconData iconeSeveridade(SeveridadeAlerta severidade) =>
    severidade == SeveridadeAlerta.contraindicacao
    ? Icons.error_outline
    : Icons.warning_amber_outlined;

/// Um alerta de segurança: severidade, texto literal e as citações que o
/// sustentam.
class ItemAlerta {
  /// Cria o item.
  const new({
    required this.severidade,
    required this.texto,
    this.fontes = const [],
  });

  /// Severidade.
  final SeveridadeAlerta severidade;

  /// Texto literal do alerta, completo.
  final String texto;

  /// Citações que sustentam o alerta; vazio enquanto o evento `citacoes` não
  /// chegou.
  final List<Citacao> fontes;
}

/// Pior severidade entre [itens] (contraindicação vence cautela).
SeveridadeAlerta severidadeMaisGrave(List<ItemAlerta> itens) =>
    itens.any((i) => i.severidade == SeveridadeAlerta.contraindicacao)
    ? SeveridadeAlerta.contraindicacao
    : SeveridadeAlerta.cautela;

/// Itens por gravidade: contraindicação primeiro, depois cautela. Dentro da
/// mesma gravidade, mantém a ordem de chegada.
List<ItemAlerta> itensPorGravidade(List<ItemAlerta> itens) => [
  ...itens.where((i) => i.severidade == SeveridadeAlerta.contraindicacao),
  ...itens.where((i) => i.severidade == SeveridadeAlerta.cautela),
];

/// Título do cabeçalho: `Alerta de segurança` ou `N alertas de segurança`.
String tituloAlertas(int quantidade) => quantidade == 1
    ? 'Alerta de segurança'
    : '$quantidade alertas de segurança';

/// Cartão de alerta de segurança (`docs/FRONTEND_SPEC.md` §24).
///
/// Um único contêiner, com fundo tingido, barra de 4 dp à esquerda e o mesmo
/// raio dos outros cartões, sem sombra. O cabeçalho aparece uma vez: ícone da
/// severidade mais alta e o título. Cada item traz o rótulo da severidade (com
/// o ícone dela), o texto literal, sem truncar, e, no fim, a linha `Fonte:`
/// com os chips daquele alerta. Itens separados por divisor.
class CartaoAlerta extends StatelessWidget {
  /// Cria o cartão para [itens]; [aoAbrirCitacao] abre o trecho de um chip.
  const new({required this.itens, this.aoAbrirCitacao, super.key});

  /// Alertas exibidos (ao menos um).
  final List<ItemAlerta> itens;

  /// Abre o trecho de uma citação; `null` desabilita o toque dos chips.
  final ValueChanged<Citacao>? aoAbrirCitacao;

  @override
  Widget build(BuildContext context) {
    final cores = context.cores;
    final tema = Theme.of(context).textTheme;
    final grave = severidadeMaisGrave(itens);
    final ordenados = itensPorGravidade(itens);
    return Semantics(
      container: true,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(raioCartao),
        child: DecoratedBox(
          decoration: BoxDecoration(color: fundoAlerta(cores, grave)),
          child: IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ExcludeSemantics(
                  child: Container(
                    width: 4,
                    color: destaqueAlerta(cores, grave),
                  ),
                ),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            ExcludeSemantics(
                              child: Icon(
                                iconeSeveridade(grave),
                                size: 20,
                                color: destaqueAlerta(cores, grave),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Semantics(
                                header: true,
                                child: Text(
                                  tituloAlertas(itens.length),
                                  style: tema.titleSmall?.copyWith(
                                    fontWeight: FontWeight.w600,
                                    color: cores.ink,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                        for (final (i, item) in ordenados.indexed) ...[
                          if (i > 0)
                            Padding(
                              padding: const EdgeInsets.symmetric(vertical: 8),
                              child: Divider(
                                height: 1,
                                color: destaqueAlerta(
                                  cores,
                                  grave,
                                ).withValues(alpha: 0.35),
                              ),
                            )
                          else
                            const SizedBox(height: 8),
                          _Item(
                            item: item,
                            comIcone: ordenados.length > 1,
                            aoAbrirCitacao: aoAbrirCitacao,
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Item extends StatelessWidget {
  const new({
    required this.item,
    required this.comIcone,
    required this.aoAbrirCitacao,
  });

  final ItemAlerta item;

  /// Com um só alerta, a linha da gravidade fica só com o rótulo.
  final bool comIcone;
  final ValueChanged<Citacao>? aoAbrirCitacao;

  @override
  Widget build(BuildContext context) {
    final cores = context.cores;
    final tema = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            if (comIcone) ...[
              ExcludeSemantics(
                child: Icon(
                  iconeSeveridade(item.severidade),
                  size: 18,
                  color: destaqueAlerta(cores, item.severidade),
                ),
              ),
              const SizedBox(width: 6),
            ],
            Flexible(
              child: Text(
                palavraSeveridade(item.severidade),
                style: tema.bodySmall?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: cores.ink,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        SelectableText(
          item.texto,
          style: tema.bodyMedium?.copyWith(color: cores.ink, height: 1.45),
        ),
        if (item.fontes.isNotEmpty)
          Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Padding(
                padding: const EdgeInsets.only(right: 4),
                child: Text(
                  'Fonte:',
                  style: tema.bodySmall?.copyWith(color: cores.inkMuted),
                ),
              ),
              for (final c in item.fontes)
                AncoraCitacao(
                  citacao: c,
                  aoTocar: aoAbrirCitacao,
                  compacta: true,
                ),
            ],
          ),
      ],
    );
  }
}

/// Barra compacta e fixa, mostrada quando o cartão saiu da tela pela rolagem:
/// `1 alerta de segurança · ver`. Um toque leva de volta ao cartão. Mesmo raio
/// do cartão; a cor segue a severidade mais alta.
class BarraAlertaCompacta extends StatelessWidget {
  /// Cria a barra para [quantidade] alertas, com a [severidade] mais grave.
  const new({
    required this.quantidade,
    required this.severidade,
    required this.aoTocar,
    super.key,
  });

  /// Quantidade de alertas.
  final int quantidade;

  /// Severidade mais grave entre os alertas.
  final SeveridadeAlerta severidade;

  /// Rola de volta até o cartão.
  final VoidCallback aoTocar;

  /// Texto da barra.
  String get texto => quantidade == 1
      ? '1 alerta de segurança · ver'
      : '$quantidade alertas de segurança · ver';

  @override
  Widget build(BuildContext context) {
    final cores = context.cores;
    return Semantics(
      button: true,
      label: texto,
      excludeSemantics: true,
      onTap: aoTocar,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(raioCartao),
        child: Material(
          color: fundoAlerta(cores, severidade),
          child: InkWell(
            onTap: aoTocar,
            child: ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 48),
              child: IntrinsicHeight(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Container(
                      width: 4,
                      color: destaqueAlerta(cores, severidade),
                    ),
                    const SizedBox(width: 12),
                    Center(
                      child: Icon(
                        iconeSeveridade(severidade),
                        size: 20,
                        color: destaqueAlerta(cores, severidade),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Align(
                        alignment: Alignment.centerLeft,
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 8),
                          child: Text(
                            texto,
                            style: Theme.of(context).textTheme.bodyMedium
                                ?.copyWith(
                                  fontWeight: FontWeight.w600,
                                  color: cores.ink,
                                ),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
