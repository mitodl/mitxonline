export function* incrementer(): Generator<number, any, any> {
  let int = 1

  // eslint-disable-next-line no-constant-condition
  while (true) {
    yield int++
  }
}
