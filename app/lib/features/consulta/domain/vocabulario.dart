import 'package:equatable/equatable.dart';

/// Fármaco do dicionário controlado, com sinônimos para o autocomplete.
class FarmacoVocabulario extends Equatable {
  /// Cria o item.
  const new({required this.nome, this.sinonimos = const []});

  /// Nome canônico — o único valor que o back-end aceita em `farmacos`.
  final String nome;

  /// Outros nomes pelos quais o fármaco é buscado.
  final List<String> sinonimos;

  @override
  List<Object?> get props => [nome, sinonimos];
}

/// Comorbidade do vocabulário controlado (toggle do §9).
class ComorbidadeVocabulario extends Equatable {
  /// Cria o item.
  const new({required this.chave, required this.rotulo});

  /// Chave enviada ao back-end.
  final String chave;

  /// Rótulo exibido ao usuário.
  final String rotulo;

  @override
  List<Object?> get props => [chave, rotulo];
}

/// Vocabulário servido por `GET /vocabulario` (`docs/FRONTEND_SPEC.md` §9).
class Vocabulario extends Equatable {
  /// Cria o vocabulário.
  const new({
    required this.versao,
    required this.especies,
    required this.farmacos,
    required this.comorbidades,
  });

  /// Hash do conteúdo, calculado pelo back-end.
  final String versao;

  /// Chaves de espécie aceitas (`canino`, `felino`).
  final List<String> especies;

  /// Fármacos do dicionário controlado.
  final List<FarmacoVocabulario> farmacos;

  /// Comorbidades aceitas.
  final List<ComorbidadeVocabulario> comorbidades;

  /// Nomes canônicos de fármacos cujo nome ou sinônimo contém [consulta]
  /// (sem distinguir caixa nem acento), exceto os de [excluir]. Os que
  /// começam pelo texto vêm primeiro.
  List<String> sugerir(String consulta, {Set<String> excluir = const {}}) {
    final q = _dobrar(consulta.trim());
    if (q.isEmpty) return const [];
    final fora = excluir.map(_dobrar).toSet();
    final inicio = <String>[];
    final meio = <String>[];
    for (final f in farmacos) {
      if (fora.contains(_dobrar(f.nome))) continue;
      final nomes = [f.nome, ...f.sinonimos].map(_dobrar);
      if (nomes.any((n) => n.startsWith(q))) {
        inicio.add(f.nome);
      } else if (nomes.any((n) => n.contains(q))) {
        meio.add(f.nome);
      }
    }
    return [...inicio, ...meio];
  }

  @override
  List<Object?> get props => [versao, especies, farmacos, comorbidades];
}

const _acentos = {
  'á': 'a', 'à': 'a', 'â': 'a', 'ã': 'a', 'é': 'e', 'ê': 'e', 'í': 'i', //
  'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ü': 'u', 'ç': 'c',
};

String _dobrar(String texto) {
  final buffer = StringBuffer();
  for (final c in texto.toLowerCase().split('')) {
    buffer.write(_acentos[c] ?? c);
  }
  return buffer.toString();
}
