# Release Checklist — 0.1.0-alpha.1

## Code
- [x] Consolidated package
- [x] CLI
- [x] REST API
- [x] local web UI
- [x] Dockerfile
- [x] unit/integration tests
- [x] CI workflow
- [x] release workflow

## Scientific
- [x] Alpha limitations disclosed
- [x] development vs blind validation distinction documented
- [x] no public scientific accuracy claim
- [ ] complete locked blind benchmark
- [ ] independent human validation

## Publication blockers in current environment
- [ ] `gh` CLI installed
- [ ] GitHub authentication established
- [ ] GitHub repository created/remote configured
- [ ] PyPI project/trusted publisher configured
- [ ] final licensing/business decision

## Recommended publication order
1. private GitHub repository
2. CI green
3. tagged GitHub alpha release
4. optional TestPyPI
5. PyPI only after package name and licensing are finalized

## Automated release gate
- Tests return code: `0`
- CLI smoke return code: `0`
- API smoke return code: `0`
- Wheel/sdist build: `PASS`
- Release gate: **PASS**
