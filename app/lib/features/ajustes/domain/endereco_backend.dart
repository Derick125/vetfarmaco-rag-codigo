import 'package:app/core/error/failures.dart';
import 'package:fpdart/fpdart.dart';

/// Normaliza o endereço digitado: sem espaços nem barra final, com esquema
/// `http` ou `https` e host.
Either<Failure, String> normalizarEndereco(String entrada) {
  final texto = entrada.trim().replaceAll(RegExp(r'/+$'), '');
  final uri = Uri.tryParse(texto);
  final valido =
      uri != null &&
      (uri.scheme == 'http' || uri.scheme == 'https') &&
      uri.host.isNotEmpty;
  if (!valido) {
    return const Left(
      FalhaValidacao('Informe um endereço completo, ex.: http://10.0.2.2:8000'),
    );
  }
  return Right(texto);
}
