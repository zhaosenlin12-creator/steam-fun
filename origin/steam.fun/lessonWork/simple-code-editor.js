/**
 * 简化版代码编辑器 - 专为课堂作品页面优化
 * 支持 Ace Editor -> Prism.js -> 简单文本显示的降级策略
 * 支持语言：C++, Python
 */
class SimpleCodeEditor {
    constructor() {
        this.editors = {};
        this.currentEditor = null;
        this.isInitialized = false;

        // 支持的语言配置
        this.languageConfig = {
            'cpp': {
                ace: 'ace/mode/c_cpp',
                prism: 'language-cpp',
                extensions: ['.cpp', '.cc', '.cxx', '.c++', '.c', '.h', '.hpp'],
                keywords: ['#include', 'int', 'main', 'return', 'void', 'class', 'struct']
            },
            'python': {
                ace: 'ace/mode/python',
                prism: 'language-python',
                extensions: ['.py', '.pyw', '.python'],
                keywords: ['def', 'import', 'from', 'class', 'if', 'elif', 'else', 'for', 'while', 'try', 'except', 'print']
            }
        };
    }

    /**
     * 智能检测代码语言
     */
    detectLanguage(code) {
        if (!code || typeof code !== 'string') {
            return 'cpp'; // 默认返回 C++
        }

        const codeLines = code.toLowerCase().split('\n');
        let cppScore = 0;
        let pythonScore = 0;

        for (const line of codeLines) {
            const trimmedLine = line.trim();

            // C++ 特征检测
            if (trimmedLine.includes('#include')) cppScore += 10;
            if (trimmedLine.includes('int main')) cppScore += 10;
            if (trimmedLine.includes('std::')) cppScore += 5;
            if (trimmedLine.includes('cout') || trimmedLine.includes('cin')) cppScore += 5;
            if (trimmedLine.includes('{') || trimmedLine.includes('}')) cppScore += 1;
            if (trimmedLine.includes(';')) cppScore += 2;

            // Python 特征检测
            if (trimmedLine.startsWith('def ')) pythonScore += 10;
            if (trimmedLine.startsWith('import ') || trimmedLine.startsWith('from ')) pythonScore += 8;
            if (trimmedLine.includes('print(')) pythonScore += 5;
            if (trimmedLine.includes('if __name__')) pythonScore += 10;
            if (trimmedLine.includes(':') && !trimmedLine.includes(';')) pythonScore += 2;
            if (trimmedLine.startsWith('class ')) pythonScore += 8;

            // Python 缩进特征
            if (line.startsWith('    ') || line.startsWith('\t')) pythonScore += 1;
        }

        // console.log(`语言检测结果: C++=${cppScore}, Python=${pythonScore}`);
        return pythonScore > cppScore ? 'python' : 'cpp';
    }

    /**
     * 初始化编辑器
     */
    async init() {
        // console.log('开始初始化简化版代码编辑器...');

        try {
            // 尝试加载 Ace Editor
            await this.loadAceEditor();
            this.currentEditor = 'ace';
            // console.log('Ace Editor 加载成功');
        } catch (error) {
            // console.warn('Ace Editor 加载失败，尝试 Prism.js:', error);

            try {
                // 尝试加载 Prism.js
                await this.loadPrismJS();
                this.currentEditor = 'prism';
                // console.log('Prism.js 加载成功');
            } catch (error) {
                // console.warn('Prism.js 加载失败，使用简单文本显示:', error);
                this.currentEditor = 'simple';
            }
        }

        this.isInitialized = true;
        return this.currentEditor;
    }

    /**
     * 加载 Ace Editor
     */
    async loadAceEditor() {
        if (window.ace) {
            return Promise.resolve();
        }

        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/ace/1.32.6/ace.js';
            script.onload = () => {
                // 并行加载语言支持和主题
                const loadPromises = [
                    this.loadAceLanguageSupport('c_cpp'),
                    this.loadAceLanguageSupport('python'),
                    this.loadAceTheme('github')  // 使用github主题，然后通过CSS自定义
                ];

                Promise.all(loadPromises)
                    .then(() => {
                        // 加载完成后添加自定义Ace样式
                        this.addCustomAceStyles();
                        resolve();
                    })
                    .catch(reject);
            };
            script.onerror = () => reject(new Error('Ace Editor 主脚本加载失败'));
            document.head.appendChild(script);
        });
    }

    /**
     * 加载 Ace Editor 语言支持
     */
    loadAceLanguageSupport(language) {
        return new Promise((resolve) => {
            const script = document.createElement('script');
            script.src = `https://cdnjs.cloudflare.com/ajax/libs/ace/1.32.6/mode-${language}.min.js`;
            script.onload = () => resolve();
            script.onerror = () => {
                // console.warn(`Ace Editor ${language} 语言支持加载失败，将使用基本模式`);
                resolve(); // 不阻断整体加载
            };
            document.head.appendChild(script);
        });
    }

    /**
     * 加载 Ace Editor 主题
     */
    loadAceTheme(theme) {
        return new Promise((resolve) => {
            const script = document.createElement('script');
            script.src = `https://cdnjs.cloudflare.com/ajax/libs/ace/1.32.6/theme-${theme}.min.js`;
            script.onload = () => resolve();
            script.onerror = () => {
                // console.warn(`Ace Editor ${theme} 主题加载失败，将使用默认主题`);
                resolve(); // 不阻断整体加载
            };
            document.head.appendChild(script);
        });
    }

    /**
     * 加载 Prism.js
     */
    async loadPrismJS() {
        if (window.Prism) {
            return Promise.resolve();
        }

        // 先添加自定义CSS样式
        this.addCustomPrismStyles();

        return new Promise((resolve, reject) => {
            // 加载 CSS - 使用基础主题，然后通过自定义样式覆盖
            const css = document.createElement('link');
            css.rel = 'stylesheet';
            css.href = 'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism.min.css';
            document.head.appendChild(css);

            // 加载 JavaScript
            const script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-core.min.js';
            script.onload = () => {
                // 并行加载语言支持
                const loadPromises = [
                    this.loadPrismLanguageSupport('cpp'),
                    this.loadPrismLanguageSupport('python')
                ];

                Promise.all(loadPromises)
                    .then(() => resolve())
                    .catch(reject);
            };
            script.onerror = () => reject(new Error('Prism.js 主脚本加载失败'));
            document.head.appendChild(script);
        });
    }

    /**
     * 加载 Prism.js 语言支持
     */
    loadPrismLanguageSupport(language) {
        return new Promise((resolve) => {
            const script = document.createElement('script');
            script.src = `https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-${language}.min.js`;
            script.onload = () => resolve();
            script.onerror = () => {
                // console.warn(`Prism.js ${language} 语言支持加载失败，将使用基本高亮`);
                resolve(); // 不阻断整体加载
            };
            document.head.appendChild(script);
        });
    }

    /**
     * 添加自定义Ace Editor样式
     */
    addCustomAceStyles() {
        const style = document.createElement('style');
        style.id = 'custom-ace-styles';
        style.textContent = `
            /* Ace Editor 自定义样式 - 丰富的颜色配置 */
            .ace_editor {
                background: #ffffff !important;
                color: #24292e !important;
            }
            
            /* 关键字 - 蓝色系 */
            .ace_editor .ace_keyword {
                color: #0000ff !important;
                font-weight: bold !important;
            }
            
            .ace_editor .ace_keyword.ace_operator {
                color: #d73a49 !important;
                font-weight: bold !important;
            }
            
            /* 字符串 - 绿色系 */
            .ace_editor .ace_string {
                color: #008000 !important;
            }
            
            .ace_editor .ace_string.ace_regexp {
                color: #22863a !important;
            }
            
            /* 注释 - 灰色系 */
            .ace_editor .ace_comment {
                color: #6a737d !important;
                font-style: italic !important;
            }
            
            .ace_editor .ace_comment.ace_doc {
                color: #6a737d !important;
                font-style: italic !important;
            }
            
            /* 函数和方法 - 紫色系 */
            .ace_editor .ace_function {
                color: #6f42c1 !important;
                font-weight: 500 !important;
            }
            
            .ace_editor .ace_entity.ace_name.ace_function {
                color: #6f42c1 !important;
                font-weight: 500 !important;
            }
            
            /* 变量和标识符 - 深蓝色 */
            .ace_editor .ace_variable {
                color: #24292e !important;
            }
            
            .ace_editor .ace_variable.ace_parameter {
                color: #e36209 !important;
            }
            
            /* 数字和常量 - 青色系 */
            .ace_editor .ace_constant.ace_numeric {
                color: #005cc5 !important;
                font-weight: 500 !important;
            }
            
            .ace_editor .ace_constant.ace_language {
                color: #005cc5 !important;
                font-weight: bold !important;
            }
            
            .ace_editor .ace_constant.ace_character {
                color: #032f62 !important;
            }
            
            /* 类型和类名 - 橙色系 */
            .ace_editor .ace_support.ace_type {
                color: #d73a49 !important;
                font-weight: 500 !important;
            }
            
            .ace_editor .ace_support.ace_class {
                color: #d73a49 !important;
                font-weight: 500 !important;
            }
            
            /* 标点符号 */
            .ace_editor .ace_paren {
                color: #24292e !important;
            }
            
            .ace_editor .ace_bracket {
                color: #24292e !important;
            }
            
            .ace_editor .ace_punctuation {
                color: #24292e !important;
            }
            
            /* C++ 特定样式 */
            .ace_editor .ace_support.ace_function.ace_C99 {
                color: #6f42c1 !important;
                font-weight: 500 !important;
            }
            
            .ace_editor .ace_support.ace_constant {
                color: #005cc5 !important;
                font-weight: bold !important;
            }
            
            .ace_editor .ace_meta.ace_preprocessor {
                color: #d73a49 !important;
                font-weight: bold !important;
            }
            
            .ace_editor .ace_meta.ace_preprocessor.ace_include {
                color: #d73a49 !important;
                font-weight: bold !important;
            }
            
            .ace_editor .ace_keyword.ace_control {
                color: #d73a49 !important;
                font-weight: bold !important;
            }
            
            /* Python 特定样式 */
            .ace_editor .ace_support.ace_function.ace_builtin.ace_python {
                color: #6f42c1 !important;
                font-weight: 500 !important;
            }
            
            .ace_editor .ace_storage.ace_type.ace_class.ace_python {
                color: #d73a49 !important;
                font-weight: bold !important;
            }
            
            .ace_editor .ace_storage.ace_type.ace_function.ace_python {
                color: #d73a49 !important;
                font-weight: bold !important;
            }
            
            .ace_editor .ace_keyword.ace_control.ace_import.ace_python {
                color: #d73a49 !important;
                font-weight: bold !important;
            }
            
            .ace_editor .ace_keyword.ace_control.ace_flow.ace_python {
                color: #d73a49 !important;
                font-weight: bold !important;
            }
            
            /* 装饰器 */
            .ace_editor .ace_meta.ace_function.ace_decorator.ace_python {
                color: #e36209 !important;
                font-weight: 500 !important;
            }
            
            /* 特殊方法 */
            .ace_editor .ace_support.ace_function.ace_magic.ace_python {
                color: #6f42c1 !important;
                font-weight: 500 !important;
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * 添加自定义Prism样式
     */
    addCustomPrismStyles() {
        const style = document.createElement('style');
        style.id = 'custom-prism-styles';
        style.textContent = `
            /* 自定义代码高亮样式 - 丰富的颜色配置 */
            
            /* 注释 - 灰色系 */
            .token.comment,
            .token.prolog,
            .token.doctype,
            .token.cdata {
                color: #6a737d !important;
                font-style: italic !important;
            }

            .token.namespace {
                opacity: .7;
            }

            /* 字符串 - 绿色系 */
            .token.string,
            .token.attr-value {
                color: #032f62 !important;
            }
            
            .token.char {
                color: #22863a !important;
            }

            /* 标点符号和操作符 */
            .token.punctuation {
                color: #24292e !important;
            }
            
            .token.operator {
                color: #d73a49 !important;
                font-weight: 500 !important;
            }

            /* 数字和常量 - 蓝色系 */
            .token.entity,
            .token.url,
            .token.symbol,
            .token.number,
            .token.boolean,
            .token.constant,
            .token.property,
            .token.regex,
            .token.inserted {
                color: #005cc5 !important;
                font-weight: 500 !important;
            }

            /* 关键字 - 红色系 */
            .token.atrule,
            .token.keyword,
            .token.attr-name,
            .language-autohotkey .token.selector {
                color: #d73a49 !important;
                font-weight: bold !important;
            }

            /* 函数 - 紫色系 */
            .token.function,
            .token.deleted,
            .language-autohotkey .token.tag {
                color: #6f42c1 !important;
                font-weight: 500 !important;
            }
            
            .token.function-name {
                color: #6f42c1 !important;
                font-weight: 500 !important;
            }

            /* 标签和选择器 */
            .token.tag,
            .token.selector,
            .language-autohotkey .token.keyword {
                color: #22863a !important;
                font-weight: 500 !important;
            }

            .token.important,
            .token.bold {
                font-weight: bold !important;
            }

            .token.italic {
                font-style: italic !important;
            }

            /* C++ 特定样式 */
            .language-cpp .token.directive.keyword,
            .language-cpp .token.macro.property {
                color: #d73a49 !important;
                font-weight: bold !important;
            }
            
            .language-cpp .token.directive {
                color: #d73a49 !important;
                font-weight: bold !important;
            }

            .language-cpp .token.string {
                color: #032f62 !important;
            }

            .language-cpp .token.keyword {
                color: #d73a49 !important;
                font-weight: bold !important;
            }

            .language-cpp .token.function {
                color: #6f42c1 !important;
                font-weight: 500 !important;
            }

            .language-cpp .token.class-name {
                color: #e36209 !important;
                font-weight: 500 !important;
            }
            
            .language-cpp .token.builtin {
                color: #005cc5 !important;
                font-weight: 500 !important;
            }
            
            .language-cpp .token.namespace {
                color: #e36209 !important;
                font-weight: 500 !important;
            }

            /* Python 特定样式 */
            .language-python .token.keyword {
                color: #d73a49 !important;
                font-weight: bold !important;
            }

            .language-python .token.string {
                color: #032f62 !important;
            }
            
            .language-python .token.string.docstring {
                color: #6a737d !important;
                font-style: italic !important;
            }

            .language-python .token.function {
                color: #6f42c1 !important;
                font-weight: 500 !important;
            }

            .language-python .token.decorator {
                color: #e36209 !important;
                font-weight: 500 !important;
            }

            .language-python .token.class-name {
                color: #e36209 !important;
                font-weight: 500 !important;
            }

            .language-python .token.builtin {
                color: #005cc5 !important;
                font-weight: 500 !important;
            }
            
            .language-python .token.boolean {
                color: #005cc5 !important;
                font-weight: bold !important;
            }
            
            .language-python .token.none {
                color: #005cc5 !important;
                font-weight: bold !important;
            }
            
            .language-python .token.triple-quoted-string {
                color: #032f62 !important;
            }

            /* 代码容器样式 */
            pre[class*="language-"] {
                background: #ffffff !important;
                border: 1px solid #e1e4e8 !important;
                border-radius: 6px !important;
                padding: 16px !important;
                overflow: auto !important;
                font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace !important;
                font-size: 14px !important;
                line-height: 1.45 !important;
                color: #24292e !important;
            }

            code[class*="language-"] {
                background: transparent !important;
                color: #24292e !important;
                font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace !important;
                font-size: 14px !important;
                line-height: 1.45 !important;
            }
            
            /* 行号样式 */
            .line-numbers .line-numbers-rows {
                border-right: 1px solid #e1e4e8 !important;
            }
            
            .line-numbers-rows > span:before {
                color: #6a737d !important;
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * 创建代码编辑器
     */
    async createEditor(containerId, code, language = null) {
        if (!this.isInitialized) {
            await this.init();
        }

        // 如果没有指定语言，自动检测
        if (!language) {
            language = this.detectLanguage(code);
        }

        const container = document.getElementById(containerId);
        if (!container) {
            throw new Error(`容器 ${containerId} 不存在`);
        }

        // 清空容器
        container.innerHTML = '';

        try {
            switch (this.currentEditor) {
                case 'ace':
                    return this.createAceEditor(container, code, language);
                case 'prism':
                    return this.createPrismEditor(container, code, language);
                default:
                    return this.createSimpleEditor(container, code);
            }
        } catch (error) {
            // console.error(`创建 ${this.currentEditor} 编辑器失败:`, error);
            // 降级到简单编辑器
            return this.createSimpleEditor(container, code);
        }
    }

    /**
     * 创建 Ace Editor
     */
    createAceEditor(container, code, language = 'cpp') {
        container.style.height = '300px';
        container.style.border = '1px solid #e1e4e8';
        container.style.borderRadius = '6px';

        const editor = window.ace.edit(container);

        // 设置主题
        try {
            editor.setTheme("ace/theme/github");
        } catch (error) {
            // console.warn('设置 Ace Editor 主题失败，使用默认主题');
        }

        // 设置语言模式
        const languageMode = this.languageConfig[language]?.ace || 'ace/mode/text';
        try {
            editor.session.setMode(languageMode);
        } catch (error) {
            // console.warn(`设置 Ace Editor 语言模式 ${languageMode} 失败，使用文本模式`);
            editor.session.setMode('ace/mode/text');
        }

        editor.setValue(code || '', -1);

        // 配置选项
        editor.setOptions({
            fontSize: 14,
            fontFamily: 'SFMono-Regular, Consolas, Liberation Mono, Menlo, monospace',
            readOnly: true,
            highlightActiveLine: false,
            highlightGutterLine: false,
            showPrintMargin: false,
            wrap: true,
            enableBasicAutocompletion: false,
            enableLiveAutocompletion: false,
            enableSnippets: false
        });

        // 隐藏光标
        editor.renderer.hideCursor();

        // 强制刷新以应用自定义样式
        setTimeout(() => {
            editor.renderer.updateFull();
        }, 100);

        // 存储编辑器实例
        this.editors[container.id] = {
            type: 'ace',
            instance: editor,
            language: language
        };

        return editor;
    }

    /**
     * 创建 Prism.js 编辑器
     */
    createPrismEditor(container, code, language = 'cpp') {
        const escapedCode = (code || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');

        const prismClass = this.languageConfig[language]?.prism || 'language-text';

        container.innerHTML = `
            <pre class="language-${language}" style="
                margin: 0;
                background: #ffffff;
                border: 1px solid #e1e4e8;
                border-radius: 6px;
                padding: 16px;
                font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
                font-size: 14px;
                line-height: 1.45;
                max-height: 400px;
                overflow-y: auto;
                color: #24292e;
            "><code class="${prismClass}">${escapedCode}</code></pre>
        `;

        // 高亮代码
        if (window.Prism) {
            try {
                window.Prism.highlightAllUnder(container);
            } catch (error) {
                // console.warn('Prism.js 代码高亮失败:', error);
            }
        }

        // 存储编辑器信息
        this.editors[container.id] = {
            type: 'prism',
            container: container,
            language: language
        };

        return container;
    }

    /**
     * 创建简单文本编辑器
     */
    createSimpleEditor(container, code) {
        container.innerHTML = `
            <pre style="
                background: #ffffff;
                border: 1px solid #e1e4e8;
                border-radius: 6px;
                padding: 16px;
                font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
                font-size: 14px;
                line-height: 1.45;
                overflow-x: auto;
                white-space: pre-wrap;
                word-wrap: break-word;
                margin: 0;
                max-height: 400px;
                overflow-y: auto;
                color: #24292e;
            "><code>${code || ''}</code></pre>
        `;

        // 存储编辑器信息
        this.editors[container.id] = {
            type: 'simple',
            container: container
        };

        return container;
    }

    /**
     * 更新编辑器内容
     */
    updateEditor(containerId, newCode, language = null) {
        const editorInfo = this.editors[containerId];
        if (!editorInfo) {
            // console.warn(`编辑器 ${containerId} 不存在`);
            return;
        }

        // 如果没有指定语言，自动检测
        if (!language) {
            language = this.detectLanguage(newCode);
        }

        try {
            switch (editorInfo.type) {
                case 'ace':
                    this.updateAceEditor(editorInfo, newCode, language);
                    break;
                case 'prism':
                    this.updatePrismEditor(editorInfo.container, newCode, language);
                    break;
                case 'simple':
                    this.updateSimpleEditor(editorInfo.container, newCode);
                    break;
            }
        } catch (error) {
            // console.error(`更新编辑器 ${containerId} 失败:`, error);
            // 降级到简单更新
            this.updateSimpleEditor(editorInfo.container, newCode);
        }
    }

    /**
     * 更新 Ace Editor
     */
    updateAceEditor(editorInfo, code, language) {
        const editor = editorInfo.instance;

        // 更新代码内容
        editor.setValue(code || '', -1);

        // 如果语言发生变化，更新语言模式
        if (language !== editorInfo.language) {
            const languageMode = this.languageConfig[language]?.ace || 'ace/mode/text';
            try {
                editor.session.setMode(languageMode);
                editorInfo.language = language;
            } catch (error) {
                // console.warn(`更新 Ace Editor 语言模式失败:`, error);
            }
        }
    }

    /**
     * 更新 Prism.js 编辑器
     */
    updatePrismEditor(container, code, language) {
        const escapedCode = (code || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');

        const prismClass = this.languageConfig[language]?.prism || 'language-text';
        const codeElement = container.querySelector('code');

        if (codeElement) {
            codeElement.className = prismClass;
            codeElement.innerHTML = escapedCode;

            if (window.Prism) {
                try {
                    window.Prism.highlightElement(codeElement);
                } catch (error) {
                    // console.warn('Prism.js 重新高亮失败:', error);
                }
            }
        }
    }

    /**
     * 更新简单编辑器
     */
    updateSimpleEditor(container, code) {
        const codeElement = container.querySelector('code');
        if (codeElement) {
            codeElement.textContent = code || '';
        }
    }

    /**
     * 销毁编辑器
     */
    destroyEditor(containerId) {
        const editorInfo = this.editors[containerId];
        if (editorInfo) {
            if (editorInfo.type === 'ace' && editorInfo.instance) {
                editorInfo.instance.destroy();
            }
            delete this.editors[containerId];
        }
    }

    /**
     * 获取当前使用的编辑器类型
     */
    getCurrentEditorType() {
        return this.currentEditor;
    }

    /**
     * 获取支持的语言列表
     */
    getSupportedLanguages() {
        return Object.keys(this.languageConfig);
    }

    /**
     * 获取编辑器信息
     */
    getEditorInfo(containerId) {
        return this.editors[containerId] || null;
    }
}

// 导出到全局
window.SimpleCodeEditor = SimpleCodeEditor; 