import 'package:app/features/consulta/domain/formulario_consulta.dart';
import 'package:app/features/consulta/domain/sanitizador.dart';
import 'package:equatable/equatable.dart';

/// Corpo exato do `POST /consulta` (`ConsultaRequest` do back-end).
class CorpoConsulta extends Equatable {
  /// Cria o corpo.
  const new({
    required this.pergunta,
    required this.complexidadeDica,
    this.especie,
    this.pesoKg,
    this.farmacos = const [],
    this.comorbidades = const [],
  });

  /// Lê o JSON gerado por [paraJson]; lança [FormatException] se estiver
  /// fora do formato.
  factory deJson(Map<String, dynamic> j) {
    try {
      return CorpoConsulta(
        pergunta: j['pergunta'] as String,
        complexidadeDica: j['complexidade_dica'] as String,
        especie: j['especie'] as String?,
        pesoKg: (j['peso_kg'] as num?)?.toDouble(),
        farmacos: ((j['farmacos'] as List<dynamic>?) ?? const [])
            .cast<String>(),
        comorbidades: ((j['comorbidades'] as List<dynamic>?) ?? const [])
            .cast<String>(),
      );
    } on Object {
      throw const FormatException('Corpo de consulta fora do formato.');
    }
  }

  /// Pergunta já sanitizada.
  final String pergunta;

  /// `alta` ou `baixa`.
  final String complexidadeDica;

  /// Chave da espécie.
  final String? especie;

  /// Peso em kg.
  final double? pesoKg;

  /// Nomes canônicos dos fármacos.
  final List<String> farmacos;

  /// Chaves das comorbidades.
  final List<String> comorbidades;

  /// JSON que sai do aparelho; campos vazios não são enviados.
  Map<String, Object?> paraJson() => {
    'pergunta': pergunta,
    'especie': ?especie,
    'peso_kg': ?pesoKg,
    if (farmacos.isNotEmpty) 'farmacos': farmacos,
    if (comorbidades.isNotEmpty) 'comorbidades': comorbidades,
    'complexidade_dica': complexidadeDica,
  };

  @override
  List<Object?> get props => [
    pergunta,
    complexidadeDica,
    especie,
    pesoKg,
    farmacos,
    comorbidades,
  ];
}

/// Monta o [CorpoConsulta] a partir do formulário, sanitizando a pergunta.
class MontarCorpoConsulta {
  /// Cria o caso de uso.
  const new(this._sanitizador);

  final Sanitizador _sanitizador;

  /// Corpo que será enviado; vale mesmo com formulário incompleto, para a
  /// prévia. Quem envia deve checar `FormularioConsulta.valido`.
  CorpoConsulta call(FormularioConsulta f) => CorpoConsulta(
    pergunta: _sanitizador.sanitizar(f.pergunta.trim()),
    complexidadeDica: f.complexidade,
    especie: f.especie,
    pesoKg: f.erroPeso == null ? f.peso : null,
    farmacos: f.farmacos,
    comorbidades: f.comorbidades.toList()..sort(),
  );
}
