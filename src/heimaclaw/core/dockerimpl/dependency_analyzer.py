"""
Dependency Analyzer - 项目依赖分析器

分析项目使用的框架/库，自动确定需要预装的依赖。
"""

import re
import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ProjectDependencies:
    """项目依赖信息"""
    python_version: str = "3.10"
    frameworks: list[str] = field(default_factory=list)
    system_deps: list[str] = field(default_factory=list)
    pip_packages: list[str] = field(default_factory=list)
    has_requirements: bool = False
    has_pyproject: bool = False
    has_env: bool = False


class DependencyAnalyzer:
    """
    项目依赖分析器
    
    分析项目使用的框架/库，自动确定需要预装的依赖。
    """
    
    # 框架特征指纹
    FRAMEWORK_PATTERNS = {
        "flask": {
            "files": ["app.py", "run.py", "wsgi.py"],
            "imports": ["flask", "werkzeug", "jinja2"],
            "system_deps": [],
        },
        "django": {
            "files": ["manage.py", "wsgi.py", "asgi.py"],
            "imports": ["django", "wsgi", "templates"],
            "system_deps": [],
        },
        "fastapi": {
            "files": ["main.py", "app.py"],
            "imports": ["fastapi", "uvicorn", "starlette"],
            "system_deps": [],
        },
        "streamlit": {
            "files": ["app.py", "main.py"],
            "imports": ["streamlit", "pandas", "plotly"],
            "system_deps": [],
        },
        "gradio": {
            "files": ["app.py", "demo.py"],
            "imports": ["gradio", "spaces"],
            "system_deps": [],
        },
        "pyqt": {
            "files": [],
            "imports": ["PyQt", "PySide", "pyside"],
            "system_deps": ["libxkbcommon0", "libxcb-icccm4", "libxcb-image0", "libxcb-keysyms1"],
        },
        "pandas": {
            "files": [],
            "imports": ["pandas", "numpy"],
            "system_deps": ["libgomp1"],
        },
        "ml": {
            "files": [],
            "imports": ["torch", "tensorflow", "transformers", "opencv"],
            "system_deps": ["libgl1", "libglib2.0-0", "libgomp1"],
        },
        "PIL": {
            "files": [],
            "imports": ["PIL", "Pillow", "cv2"],
            "system_deps": ["libjpeg-dev", "libpng-dev", "zlib1g-dev"],
        },
        "mysql": {
            "files": [],
            "imports": ["mysql", "pymysql", "mysql-connector"],
            "system_deps": ["libmysqlclient-dev"],
        },
        "postgresql": {
            "files": [],
            "imports": ["psycopg2", "asyncpg"],
            "system_deps": ["libpq-dev"],
        },
        "redis": {
            "files": [],
            "imports": ["redis", "aioredis"],
            "system_deps": [],
        },
        "elasticsearch": {
            "files": [],
            "imports": ["elasticsearch", "es"],
            "system_deps": [],
        },
    }
    
    def analyze(self, project_dir: Path) -> ProjectDependencies:
        """
        分析项目依赖
        
        Args:
            project_dir: 项目目录路径
            
        Returns:
            ProjectDependencies 对象
        """
        result = ProjectDependencies()
        
        project_dir = Path(project_dir)
        if not project_dir.exists():
            return result
        
        # 1. 检测依赖文件
        if (project_dir / "requirements.txt").exists():
            result.has_requirements = True
            result.pip_packages.extend(self._parse_requirements(project_dir / "requirements.txt"))
        
        if (project_dir / "pyproject.toml").exists():
            result.has_pyproject = True
            result.pip_packages.extend(self._parse_pyproject(project_dir / "pyproject.toml"))
        
        if (project_dir / "environment.yml").exists():
            result.has_env = True
        
        # 2. 扫描 Python 文件检测框架
        result.frameworks = self._detect_frameworks(project_dir)
        
        # 3. 从 Python 文件提取导入的包
        imports = self._extract_imports(project_dir)
        result.pip_packages.extend(imports)
        
        # 4. 检测系统依赖
        result.system_deps = self._detect_system_deps(result.frameworks)
        
        # 5. 去重
        result.pip_packages = list(set(result.pip_packages))
        result.system_deps = list(set(result.system_deps))
        
        return result
    
    def _detect_frameworks(self, project_dir: Path) -> list[str]:
        """检测项目使用的框架"""
        detected = set()
        
        for py_file in project_dir.rglob("*.py"):
            try:
                content = py_file.read_text(errors="ignore")
                
                for framework, info in self.FRAMEWORK_PATTERNS.items():
                    # 检查文件特征
                    for filename in info["files"]:
                        if py_file.name == filename:
                            detected.add(framework)
                    
                    # 检查导入
                    for import_name in info["imports"]:
                        if import_name in content:
                            detected.add(framework)
            
            except Exception:
                continue
        
        return list(detected)
    
    def _extract_imports(self, project_dir: Path) -> list[str]:
        """从 Python 文件提取导入的包"""
        packages = set()
        
        for py_file in project_dir.rglob("*.py"):
            try:
                content = py_file.read_text(errors="ignore")
                tree = ast.parse(content, filename=str(py_file))
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            pkg = alias.name.split(".")[0]
                            if not pkg.startswith("_"):
                                packages.add(pkg)
                    
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            pkg = node.module.split(".")[0]
                            if not pkg.startswith("_"):
                                packages.add(pkg)
            
            except Exception:
                continue
        
        return list(packages)
    
    def _detect_system_deps(self, frameworks: list[str]) -> list[str]:
        """检测需要的系统依赖"""
        all_deps = set()
        
        for fw in frameworks:
            info = self.FRAMEWORK_PATTERNS.get(fw, {})
            all_deps.update(info.get("system_deps", []))
        
        return list(all_deps)
    
    def _parse_requirements(self, req_file: Path) -> list[str]:
        """解析 requirements.txt"""
        packages = []
        
        try:
            content = req_file.read_text()
            
            for line in content.splitlines():
                line = line.strip()
                
                # 跳过空行和注释
                if not line or line.startswith("#"):
                    continue
                
                # 跳过 URL 安装和本地路径
                if line.startswith(("http://", "https://", "git+", "-e", "./", "../")):
                    continue
                
                # 提取包名（去除版本约束）
                pkg = re.split(r"[<>=!~]", line)[0].strip()
                if pkg:
                    packages.append(pkg)
        
        except Exception:
            pass
        
        return packages
    
    def _parse_pyproject(self, pyproject_file: Path) -> list[str]:
        """解析 pyproject.toml"""
        packages = []
        
        try:
            content = pyproject_file.read_text()
            
            # 简单解析 dependencies 部分
            in_deps = False
            for line in content.splitlines():
                line = line.strip()
                
                if line.startswith("dependencies"):
                    in_deps = True
                    continue
                
                if in_deps:
                    if line.startswith("["):
                        break
                    
                    # 提取包名
                    match = re.match(r'"([^"<>>=!~]+)', line)
                    if match:
                        pkg = match.group(1).split(".")[0]
                        if not pkg.startswith("_"):
                            packages.append(pkg)
        
        except Exception:
            pass
        
        return packages
    
    def generate_dockerfile(
        self,
        project_dir: Path,
        base_image: str = "python:3.10-slim",
    ) -> str:
        """
        生成项目专用的 Dockerfile
        
        Args:
            project_dir: 项目目录
            base_image: 基础镜像
            
        Returns:
            Dockerfile 内容
        """
        deps = self.analyze(project_dir)
        
        lines = [
            f"FROM {base_image}",
            "",
            "# 安装系统依赖",
        ]
        
        if deps.system_deps:
            lines.append(f"RUN apt-get update && apt-get install -y \\")
            for dep in deps.system_deps:
                lines.append(f"    {dep} \\")
            lines.append("    && rm -rf /var/lib/apt/lists/*")
        else:
            lines.append("RUN true")
        
        lines.extend([
            "",
            "# 设置环境变量",
            "ENV PYTHONUNBUFFERED=1",
            "ENV DEBIAN_FRONTEND=noninteractive",
            "",
            "# 设置工作目录",
            "WORKDIR /root/workspace",
            "",
            "# 默认命令",
            'CMD ["sleep", "infinity"]',
        ])
        
        return "\n".join(lines)


# 全局实例
_analyzer: Optional[DependencyAnalyzer] = None


def get_dependency_analyzer() -> DependencyAnalyzer:
    """获取全局依赖分析器实例"""
    global _analyzer
    if _analyzer is None:
        _analyzer = DependencyAnalyzer()
    return _analyzer
