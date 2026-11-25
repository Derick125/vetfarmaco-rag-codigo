import 'dart:convert';

import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:crypto/crypto.dart';
import 'package:equatable/equatable.dart';

/// Chave estável de uma consulta: mesmo corpo enviado, mesma chave.
///
/// SHA-256 sobre o JSON do corpo, truncado em 16 caracteres hexadecimais
/// (as chaves do `hive_ce` têm no máximo 255 caracteres; a pergunta pode ter
/// 4000).
String chaveDaConsulta(CorpoConsulta corpo) => sha256
    .convert(utf8.encode(jsonEncode(corpo.paraJson())))
    .toString()
    .substring(0, 16);

/// Resposta validada, guardada para leitura offline (`FRONTEND_SPEC.md` §5).
class RespostaSalva extends Equatable {
  /// Cria a resposta salva.
  const new({
    required this.corpo,
    required this.paragrafos,
    required this.citacoes,
    required this.fim,
    required this.geradaEm,
    this.alerta,
  });

  /// Consulta que originou a resposta.
  final CorpoConsulta corpo;

  /// Parágrafos validados.
  final List<EventoParagrafo> paragrafos;

  /// Citações validadas.
  final List<Citacao> citacoes;

  /// Alerta de segurança, se houve.
  final EventoAlerta? alerta;

  /// `fim` original: confiança, versão do modelo, tempos.
  final EventoFim fim;

  /// Quando a resposta foi gerada.
  final DateTime geradaEm;

  /// Chave de cache da consulta.
  String get chave => chaveDaConsulta(corpo);

  /// Houve alerta de segurança (ponto colorido do histórico).
  bool get temAlerta => alerta != null;

  @override
  List<Object?> get props => [
    corpo,
    paragrafos,
    citacoes,
    alerta,
    fim,
    geradaEm,
  ];
}
