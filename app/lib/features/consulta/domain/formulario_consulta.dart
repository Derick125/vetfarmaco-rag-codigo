import 'package:equatable/equatable.dart';

/// Peso máximo aceito pelo back-end (`ConsultaRequest.peso_kg`).
const pesoMaximoKg = 200.0;

/// Tamanho mínimo da pergunta (`ConsultaRequest.pergunta`).
const minimoPergunta = 3;

/// Tamanho máximo da pergunta (`ConsultaRequest.pergunta`).
const maximoPergunta = 4000;

final _posologica = RegExp(
  r'\b(dose|doses|dosagem|posologia|quanto|quantos|intervalo|frequ[eê]ncia|a cada)\b|\d\s*(mg|ml|mcg)\b',
  caseSensitive: false,
);

/// Interpreta o peso digitado ("4,2" ou "4.2"). `null` se vazio ou inválido.
double? interpretarPeso(String texto) =>
    double.tryParse(texto.trim().replaceAll(',', '.'));

/// Campos estruturados da consulta (`docs/FRONTEND_SPEC.md` §9).
///
/// Só vocabulário controlado e números: nome do tutor ou do animal nunca
/// tem onde entrar (`CLAUDE.md` §4.3).
class FormularioConsulta extends Equatable {
  /// Cria o formulário.
  const new({
    this.especie,
    this.pesoTexto = '',
    this.farmacos = const [],
    this.comorbidades = const {},
    this.pergunta = '',
  });

  /// Chave da espécie escolhida, ou `null`.
  final String? especie;

  /// Peso como digitado, para não reescrever o campo enquanto se digita.
  final String pesoTexto;

  /// Nomes canônicos dos fármacos, na ordem de inclusão.
  final List<String> farmacos;

  /// Chaves das comorbidades marcadas.
  final Set<String> comorbidades;

  /// Pergunta como digitada (ainda sem sanitização).
  final String pergunta;

  /// Peso em kg, ou `null` se vazio ou ilegível.
  double? get peso => interpretarPeso(pesoTexto);

  /// Mensagem de erro do peso, ou `null` se vazio ou válido.
  String? get erroPeso {
    if (pesoTexto.trim().isEmpty) return null;
    final p = peso;
    if (p == null || p <= 0 || p > pesoMaximoKg) {
      return 'Informe um peso entre 0 e 200 kg.';
    }
    return null;
  }

  /// A pergunta pede dose, frequência ou quantidade (heurística do §9).
  bool get perguntaPosologica => _posologica.hasMatch(pergunta);

  /// Peso ausente numa pergunta posológica.
  bool get faltaPeso => perguntaPosologica && peso == null && erroPeso == null;

  /// Pergunta com o mínimo que o back-end aceita (3 caracteres).
  bool get temPergunta => pergunta.trim().length >= minimoPergunta;

  /// Espécie e pergunta obrigatórias; peso válido e, se a pergunta é
  /// posológica, obrigatório (`docs/FRONTEND_SPEC.md` §9).
  bool get valido =>
      especie != null && temPergunta && erroPeso == null && !faltaPeso;

  /// Aviso (não bloqueia): recomenda ao menos um fármaco.
  bool get semFarmacos => farmacos.isEmpty;

  /// Dica de complexidade para o roteador de `thinking_level`
  /// (`docs/FRONTEND_SPEC.md` §9): alta com 2+ fármacos ou uma comorbidade.
  String get complexidade =>
      farmacos.length >= 2 || comorbidades.isNotEmpty ? 'alta' : 'baixa';

  /// Cópia com campos trocados.
  FormularioConsulta copiar({
    String? Function()? especie,
    String? pesoTexto,
    List<String>? farmacos,
    Set<String>? comorbidades,
    String? pergunta,
  }) => FormularioConsulta(
    especie: especie != null ? especie() : this.especie,
    pesoTexto: pesoTexto ?? this.pesoTexto,
    farmacos: farmacos ?? this.farmacos,
    comorbidades: comorbidades ?? this.comorbidades,
    pergunta: pergunta ?? this.pergunta,
  );

  @override
  List<Object?> get props => [
    especie,
    pesoTexto,
    farmacos,
    comorbidades,
    pergunta,
  ];
}
