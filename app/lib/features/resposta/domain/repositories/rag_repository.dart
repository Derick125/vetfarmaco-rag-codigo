import 'package:app/core/error/failures.dart';
import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:fpdart/fpdart.dart';

/// Acesso ao back-end RAG (`docs/ARCHITECTURE.md` §3).
abstract interface class RagRepository {
  /// Envia a consulta (já sanitizada) e emite os eventos validados.
  ///
  /// Uma `Left` encerra o stream; o consumidor descarta o que for preciso
  /// conforme a falha (`FalhaCitacao` invalida tudo).
  Stream<Either<Failure, EventoResposta>> consultar(CorpoConsulta corpo);
}
