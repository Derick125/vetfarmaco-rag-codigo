import 'package:app/core/error/failures.dart';
import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:app/features/resposta/domain/repositories/rag_repository.dart';
import 'package:fpdart/fpdart.dart';

/// Envia a consulta e devolve o stream de eventos.
///
/// A sanitização já aconteceu em `MontarCorpoConsulta`: o [CorpoConsulta]
/// é exatamente o que o usuário viu em "Ver o que será enviado".
class RealizarConsulta {
  /// Cria o caso de uso.
  const new(this._repositorio);

  final RagRepository _repositorio;

  /// Eventos da resposta, ou a falha que encerrou o stream.
  Stream<Either<Failure, EventoResposta>> call(CorpoConsulta corpo) =>
      _repositorio.consultar(corpo);
}
