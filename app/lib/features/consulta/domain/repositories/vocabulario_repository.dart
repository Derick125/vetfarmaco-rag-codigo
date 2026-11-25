import 'package:app/core/error/failures.dart';
import 'package:app/features/consulta/domain/vocabulario.dart';
import 'package:fpdart/fpdart.dart';

/// Origem do vocabulário controlado: servidor, com cópia local offline.
abstract interface class VocabularioRepository {
  /// Busca `GET /vocabulario` e atualiza a cópia local; se o servidor não
  /// responder, devolve a cópia local. `Left` só quando não há nenhuma.
  Future<Either<Failure, Vocabulario>> obter();
}
