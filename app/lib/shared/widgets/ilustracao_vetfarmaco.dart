import 'package:flutter/material.dart';

/// Cenas do conjunto de ilustrações.
///
/// Os SVG ficam em `assets/arte_fonte/` e os PNG, em `assets/img/` (exportados
/// por `tool/exportar_png.py`). Autoria: `docs/CREDITOS_ARTE.md`.
enum Cena {
  /// Cão e gato com o ícone da marca (abertura).
  abertura('abertura', 300),

  /// Cão e gato com um livro aberto (introdução, cartão 1).
  introCartao1('intro_cartao1', 296),

  /// Celular com respostas salvas, selo de data e símbolo de «sem rede»
  /// (introdução, cartão 3).
  introCartao3('intro_cartao3', 296),

  /// Gato dormindo sobre livros (histórico vazio).
  historicoVazio('historico_vazio', 310),

  /// Faixa com cão, gato, cápsula e frasco (tela Sobre).
  sobreFaixa('sobre_faixa', 412),

  /// Cão e gato pequenos (cabeçalho da tela inicial).
  inicioCabecalho('inicio_cabecalho', 150);

  new(this.arquivo, this.larguraPadrao);

  /// Nome-base dos arquivos em `assets/img/`, sem o tema nem a extensão.
  final String arquivo;

  /// Largura, em dp, com que a cena aparece; é também o tamanho 1x do PNG.
  final double larguraPadrao;
}

/// Ilustração decorativa em PNG, no tema atual (claro ou escuro).
///
/// A densidade (1x, 2x ou 3x) é escolhida pelo `Image.asset`. A ilustração
/// some do leitor de tela e **não** pode aparecer na nova consulta, na
/// resposta, no alerta, em `Sem evidência`, `Sem conexão`, falha ou tempo
/// esgotado: nas telas clínicas a sobriedade é intencional
/// (`docs/FRONTEND_SPEC.md` §26).
class IlustracaoVetFarmaco extends StatelessWidget {
  /// Cria a ilustração de [cena]; [largura] troca a largura padrão.
  const new({required this.cena, this.largura, super.key});

  /// Cena exibida.
  final Cena cena;

  /// Largura em dp, ou `null` para a padrão da cena.
  final double? largura;

  /// Caminho do PNG 1x de [cena] no tema indicado.
  static String caminho(Cena cena, {required bool escuro}) =>
      'assets/img/${cena.arquivo}_${escuro ? 'escuro' : 'claro'}.png';

  @override
  Widget build(BuildContext context) {
    final escuro = Theme.of(context).brightness == Brightness.dark;
    final w = largura ?? cena.larguraPadrao;
    return Image.asset(
      caminho(cena, escuro: escuro),
      width: w,
      excludeFromSemantics: true,
      errorBuilder: (context, erro, pilha) => SizedBox(width: w),
    );
  }
}
