# Code Review Checklist（AI + 人工）

- [ ] 代码是否符合 PEP8 / ruff 规范
- [ ] 接口契约是否完整（Pydantic）
- [ ] 是否有安全漏洞（注入、权限越界）
- [ ] 异常处理是否全面
- [ ] 日志级别是否合理
- [ ] 性能风险点是否标注
- [ ] 代码、注释、字符串中无 emoji
   - [ ] 日志使用 rich 颜色区分，且支持 NO_COLOR
   - [ ] 注释使用简体中文，docstring 完整

