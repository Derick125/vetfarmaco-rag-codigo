import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/consulta/domain/formulario_consulta.dart';
import 'package:app/features/consulta/domain/vocabulario.dart';
import 'package:equatable/equatable.dart';

/// Situação do carregamento do vocabulário.
enum StatusVocabulario {
  /// Buscando no servidor.
  carregando,

  /// Disponível (do servidor ou da cópia local).
  pronto,

  /// Sem servidor e sem cópia local; veja `ConsultaState.mensagem`.
  falha,
}

/// Estado de `/consulta`: vocabulário e formulário (`FRONTEND_SPEC.md` §9).
class ConsultaState extends Equatable {
  /// Cria o estado.
  const new({
    this.status = StatusVocabulario.carregando,
    this.vocabulario,
    this.formulario = const FormularioConsulta(),
    this.mensagem,
    this.corpo,
  });

  /// Situação do vocabulário.
  final StatusVocabulario status;

  /// Vocabulário carregado, se houver.
  final Vocabulario? vocabulario;

  /// Campos preenchidos.
  final FormularioConsulta formulario;

  /// Mensagem de falha do carregamento.
  final String? mensagem;

  /// Corpo sanitizado que seria enviado agora (prévia).
  final CorpoConsulta? corpo;

  /// Cópia com campos trocados; [mensagem] é sempre substituída.
  ConsultaState copiar({
    StatusVocabulario? status,
    Vocabulario? vocabulario,
    FormularioConsulta? formulario,
    String? mensagem,
    CorpoConsulta? corpo,
  }) => ConsultaState(
    status: status ?? this.status,
    vocabulario: vocabulario ?? this.vocabulario,
    formulario: formulario ?? this.formulario,
    mensagem: mensagem,
    corpo: corpo ?? this.corpo,
  );

  @override
  List<Object?> get props => [status, vocabulario, formulario, mensagem, corpo];
}
