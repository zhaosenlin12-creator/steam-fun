/* eslint-disable */
// 获取URL参数的工具方法
function getUrlParam(paramName) {
    const queryString = window.location.search;
    const urlParams = new URLSearchParams(queryString);
    return urlParams.get(paramName);
}

// 全屏状态管理器
const FullscreenManager = {
    isFullscreen: false,
    currentIframe: null,
    listeners: [],

    // 设置全屏状态
    setFullscreenState(isFullscreen, iframe = null) {
        this.isFullscreen = isFullscreen;
        if (iframe) {
            this.currentIframe = iframe;
        }

        // 通知所有监听器
        this.listeners.forEach(listener => {
            try {
                listener(isFullscreen, this.currentIframe);
            } catch (error) {
                // console.error('全屏监听器执行错误:', error);
            }
        });
    },

    // 添加监听器
    addListener(callback) {
        if (typeof callback === 'function') {
            this.listeners.push(callback);
        }
    },

    // 移除监听器
    removeListener(callback) {
        const index = this.listeners.indexOf(callback);
        if (index > -1) {
            this.listeners.splice(index, 1);
        }
    },

    // 获取当前状态
    getState() {
        return this.isFullscreen;
    },

    // 获取当前iframe
    getCurrentIframe() {
        return this.currentIframe;
    }
};

// 页面配置
const CONFIG = {
    selectors: {
        projectTitle: '.title-text',
        teacherInfo: '.info-item:nth-child(1) .info-text',
        publishTime: '.info-item:nth-child(2) .info-text',
        studentInfo: '.info-item:nth-child(3) .info-text',
        workStudentName: '.project-info-item:nth-child(4) .info-text',
        workPublishTime: '.project-info-item:nth-child(5) .info-text',
        tagList: '.project-tag .tag-item',
        introText: '.intro-text',
        operationText: '.operation-text',
        ratingStars: '.stars-container',
        reviewText: '.review-text',
        ctaButton: '.cta-button span:last-child',
        codeTagBox: '.code-tag-box',
        codeEditor: '#monaco_editor',
        codeBox: '.code-box',
        iframeElement: 'iframe',
        imageContainer: '.image-container',
        workBox: '.work-box',
        workImg: '.work-img img',
        workTitleText: '.work-title-text',
        workType: '.work-type'
    },
    templates: {
        teacher: '指导老师 {teacherName}',
        publishTime: '发布时间 {publishTime}',
        student: '学生作者 {studentName}',
        workPublishTime: '{workPublishTime}',
        workStudentName: '{workStudentName}',
        rating: (rating) => {
            const fullStars = Math.floor(rating);
            const hasHalfStar = rating % 1 !== 0;
            let starsHTML = '';

            for (let i = 0; i < 5; i++) {
                if (i < fullStars) {
                    // 已评价星星 - 实心SVG
                    starsHTML += `<svg class="star-icon filled" viewBox="0 0 1026 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" width="5vw" height="5vw">
                        <path d="M559.826357 38.096844l114.290533 234.930541c6.349474 19.048422 25.397896 31.74737 44.446319 31.74737l247.629488 38.096844c50.795792 6.349474 69.844215 69.844215 31.74737 107.941059L820.154794 634.947406c-12.698948 12.698948-19.048422 31.74737-19.048422 57.145267l44.446318 260.328436c6.349474 50.795792-44.446318 88.892637-82.543163 63.494741l-222.231592-120.640008c-19.048422-6.349474-38.096844-6.349474-57.145266 0L261.401076 1015.91585c-44.446318 25.397896-95.242111-12.698948-82.543162-63.494741l44.446318-260.328436c6.349474-19.048422 0-38.096844-19.048422-57.145267L20.121062 444.463184c-38.096844-31.74737-19.048422-95.242111 31.74737-101.591585l247.629489-38.096844c19.048422 0 38.096844-12.698948 44.446318-31.74737L458.234772 38.096844c19.048422-50.795792 82.543163-50.795792 101.591585 0z" fill="#FBBF24"></path>
                    </svg>`;
                } else if (i === fullStars && hasHalfStar) {
                    // 半星 - 实心SVG（可以后续添加半星样式）
                    starsHTML += `<svg class="star-icon half" viewBox="0 0 1026 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" width="5vw" height="5vw">
                        <path d="M559.826357 38.096844l114.290533 234.930541c6.349474 19.048422 25.397896 31.74737 44.446319 31.74737l247.629488 38.096844c50.795792 6.349474 69.844215 69.844215 31.74737 107.941059L820.154794 634.947406c-12.698948 12.698948-19.048422 31.74737-19.048422 57.145267l44.446318 260.328436c6.349474 50.795792-44.446318 88.892637-82.543163 63.494741l-222.231592-120.640008c-19.048422-6.349474-38.096844-6.349474-57.145266 0L261.401076 1015.91585c-44.446318 25.397896-95.242111-12.698948-82.543162-63.494741l44.446318-260.328436c6.349474-19.048422 0-38.096844-19.048422-57.145267L20.121062 444.463184c-38.096844-31.74737-19.048422-95.242111 31.74737-101.591585l247.629489-38.096844c19.048422 0 38.096844-12.698948 44.446318-31.74737L458.234772 38.096844c19.048422-50.795792 82.543163-50.795792 101.591585 0z" fill="#FBBF24"></path>
                    </svg>`;
                } else {
                    // 未评价星星 - 空心SVG
                    starsHTML += `<svg class="star-icon empty" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" width="5vw" height="5vw">
                        <path d="M791.2 1018.4c-8.8 0-16.8-2.4-24.8-6.4l-224-123.2c-9.6-4.8-20-8-30.4-8-10.4 0-20.8 2.4-30.4 8l-224 123.2c-8 4-16 6.4-24.8 6.4-15.2 0-30.4-7.2-40.8-19.2-11.2-12.8-15.2-29.6-12.8-47.2l43.2-260.8c4-21.6-3.2-44-18.4-59.2L21.6 446.4A57.6 57.6 0 0 1 8 387.2c6.4-20 23.2-34.4 43.2-37.6l250.4-38.4c20.8-3.2 39.2-16.8 48.8-36.8l112-237.6C472 16.8 489.6 5.6 511.2 5.6c20.8 0 39.2 12 48 31.2l112 237.6c9.6 20 28 33.6 48.8 36.8l250.4 38.4c20 3.2 36.8 16.8 43.2 37.6 7.2 20.8 1.6 44-13.6 59.2l-181.6 184.8c-15.2 15.2-22.4 37.6-18.4 59.2l43.2 260.8c3.2 17.6-1.6 34.4-12.8 47.2-8.8 12.8-23.2 20-39.2 20zM512 831.2c19.2 0 37.6 4.8 54.4 13.6l236.8 130.4-6.4-14.4v-0.8l-42.4-260.8c-6.4-37.6 5.6-76 32-102.4L968 412c2.4-2.4 3.2-6.4 1.6-9.6v-3.2l-256-39.2c-37.6-5.6-69.6-29.6-86.4-64.8L512 50.4 396 295.2c-16.8 35.2-48.8 59.2-86.4 64.8L49.6 400l5.6 5.6c0 1.6 0.8 4 2.4 6.4l181.6 184.8c26.4 26.4 38.4 64.8 32 102.4L228 960v4l1.6 7.2 228.8-125.6c16-9.6 34.4-14.4 53.6-14.4z" fill="#FBBF24"></path>
                    </svg>`;
                }
            }
            return starsHTML;
        }
    }
};

// 代码数据管理
const CodeDataManager = {
    codeData: {
        codeId: '',
        code: '',
        codeList: [],
        subjectCode: null,
        useIframe: false
    },

    setCodeData(data) {
        this.codeData = { ...this.codeData, ...data };
    },

    getCodeData() {
        return this.codeData;
    },

    updateCurrentCode(codeId, code) {
        this.codeData.codeId = codeId;
        this.codeData.code = code;
    },

    // 根据科目类型处理不同的数据结构
    processCodeData(data) {
        const { tchWork, subject_code } = data;
        this.codeData.subjectCode = subject_code;

        switch (subject_code) {
            case 1: // jr
            case 2: // sc
                this.processJrScData(tchWork, subject_code);
                break;
            case 3: // py
                this.processPyData(tchWork);
                break;
            case 4: // cpp
                this.processCppData(tchWork);
                break;
            default:
                // console.warn('未知的科目类型:', subject_code);
                this.processDefaultData(tchWork);
        }
    },

    // 处理jr和sc类型的数据
    processJrScData(tchWork, subjectCode) {
        if (tchWork?.work_url) {
            let finalUrl = '';

            if (subjectCode === 1) {
                // subjectCode == 1 (JR): 使用 /jrcode/h5show1.html?mode=look&filepath= + work_url
                finalUrl = '/jrcode/h5show.html?mode=look&filepath=' + tchWork.work_url;
            } else if (subjectCode === 2) {
                // subjectCode == 2 (SC): 使用 /scratch/h5player1.html 带多个参数
                let tchWorkInfo = {
                    work_url: '',
                    title: '',
                    name: '',
                }
                tchWorkInfo.name = tchWork.name;
                tchWorkInfo.title = tchWork.title;
                tchWorkInfo.work_url = tchWork.work_url;
                const baseWidth = window.innerWidth || 750;
                finalUrl = `/scratch/h5player1.html?scoure=MiniWorksDetails&basePageWidth=${baseWidth}&marginVal=20&work_type=2` +
                    '&work_id=' + tchWork.id +
                    '&subject_code=2' +
                    '&tchWorkInfo=' + JSON.stringify(tchWorkInfo);
            }

            // 当subjectCode等于1或2时，不运行编辑器，直接使用iframe
            this.setCodeData({
                codeId: 'iframe',
                code: finalUrl,
                codeList: [],
                useIframe: true,
                subjectCode: subjectCode
            });
        }
    },

    // 处理py类型的数据
    processPyData(tchWork) {
        if (tchWork?.work_url) {
            try {
                // 尝试解析JSON格式的代码数据（与subjectCode==4相同的格式）
                const codeList = JSON.parse(tchWork.work_url);
                if (Array.isArray(codeList) && codeList.length > 0) {
                    // 将解析后的数据转换为标准格式
                    const processedCodeList = codeList.map(item => ({
                        id: item.id,
                        code: item.code || '',
                        label: item.label || `代码${item.id}`,
                        language: this.getLanguageFromType(item.type) || 2, // 默认Python
                        type: item.type
                    }));

                    this.setCodeData({
                        codeId: processedCodeList[0].id,
                        code: processedCodeList[0].code,
                        codeList: processedCodeList
                    });

                } else {
                    // 如果不是数组，作为单个Python代码处理
                    this.setCodeData({
                        codeId: 'python',
                        code: tchWork.work_url,
                        codeList: [{ id: 'python', code: tchWork.work_url, label: 'Python代码', language: 2 }]
                    });
                }
            } catch (error) {
                // console.warn('解析work_url失败，作为普通Python代码处理:', error);
                // 如果解析失败，作为普通Python代码处理
                this.setCodeData({
                    codeId: 'python',
                    code: tchWork.work_url,
                    codeList: [{ id: 'python', code: tchWork.work_url, label: 'Python代码', language: 2 }]
                });
            }
        }
    },

    // 处理cpp类型的数据
    processCppData(tchWork) {
        // 当subjectCode==4时，work_url包含JSON格式的代码列表
        if (tchWork?.work_url) {
            try {
                // 解析work_url中的JSON数据
                const codeList = JSON.parse(tchWork.work_url);
                if (Array.isArray(codeList) && codeList.length > 0) {
                    // 将解析后的数据转换为标准格式
                    const processedCodeList = codeList.map(item => ({
                        id: item.id,
                        code: item.code || '',
                        label: item.label || `代码${item.id}`,
                        language: this.getLanguageFromType(item.type) || 1, // 默认C++
                        type: item.type
                    }));

                    this.setCodeData({
                        codeId: processedCodeList[0].id,
                        code: processedCodeList[0].code,
                        codeList: processedCodeList
                    });

                } else {
                    // console.warn('解析work_url后不是有效的数组');
                }
            } catch (error) {
                // console.error('解析work_url JSON失败:', error);
                // 如果解析失败，尝试使用cppLessonOjProblemRelationList
                this.processCppProblemList(tchWork);
            }
        } else {
            // 如果没有work_url，尝试使用cppLessonOjProblemRelationList
            this.processCppProblemList(tchWork);
        }
    },

    // 处理cppLessonOjProblemRelationList数据
    processCppProblemList(tchWork) {
        if (tchWork?.cppLessonOjProblemRelationList && Array.isArray(tchWork.cppLessonOjProblemRelationList)) {
            const codeList = tchWork.cppLessonOjProblemRelationList.map(item => ({
                id: item.id,
                code: item.submissionInfo?.code || '',
                label: item.oj_problem_title || `题目${item.id}`,
                language: item.submissionInfo?.language || 1
            }));

            if (codeList.length > 0) {
                this.setCodeData({
                    codeId: codeList[0].id,
                    code: codeList[0].code,
                    codeList: codeList
                });
            }
        } else {
            // console.warn('没有找到有效的C++代码数据');
        }
    },

    // 处理默认数据
    processDefaultData(tchWork) {
        if (tchWork?.work_url) {
            this.setCodeData({
                codeId: 'default',
                code: tchWork.work_url,
                codeList: [{ id: 'default', code: tchWork.work_url, label: '代码' }]
            });
        }
    },

    // 根据type字段获取语言类型
    getLanguageFromType(type) {
        const typeMap = {
            'py': 2,    // Python
            'cpp': 1,   // C++
            'js': 3,    // JavaScript
            'java': 4   // Java
        };
        return typeMap[type] || 1; // 默认C++
    }
};

// 数据管理模块
const DataManager = {
    pageData: null,

    async fetchData(params) {
        return new Promise((resolve, reject) => {
            // 检查必要的函数是否存在
            if (params.stuTchPlanId) {
                if (!window.h5GetTchWorkContent) {
                    // console.error('h5GetTchWorkContent 函数不存在');
                    reject(new Error('h5GetTchWorkContent 函数不存在'));
                    return;
                }
            } else {
                if (!window.h5GetWorkContentForNew) {
                    // console.error('h5GetWorkContentForNew 函数不存在');
                    reject(new Error('h5GetWorkContentForNew 函数不存在'));
                    return;
                }
            }
            if (params.stuTchPlanId) {
                try {
                    window.h5GetTchWorkContent(
                        params.workId,
                        params.subjectCode,
                        params.eduId,
                        params.stuTchPlanId,
                        (info) => {

                            // 验证返回的数据
                            if (!info) {
                                // console.error('返回的数据为空');
                                reject(new Error('返回的数据为空'));
                                return;
                            }

                            this.pageData = info;
                            resolve(info);
                        }
                    );
                } catch (error) {
                    // console.error('调用 h5GetTchWorkContent 失败:', error);
                    reject(error);
                }
            } else {
                try {
                    window.h5GetWorkContentForNew(
                        params.eduId,
                        params.workId,
                        params.subjectCode,
                        (info) => {
                            // 验证返回的数据
                            if (!info) {
                                // console.error('返回的数据为空');
                                reject(new Error('返回的数据为空'));
                                return;
                            }
                            if (Number(params.subjectCode) === 4) {
                                info.work.cppLessonOjProblemRelationList = [{
                                    id: 1,
                                    oj_problem_title: info.work.title,
                                    submissionInfo: {
                                        code: info.work.work_url,
                                        language: 1
                                    }
                                }]
                                info.work.work_url = '';
                            }
                            info.tchWork = info.work;
                            this.pageData = info;
                            resolve(info);
                        }
                    );
                } catch (error) {
                    // console.error('调用 h5GetWorkContentForNew 失败:', error);
                    reject(error);
                }
            }
        });
    },

    getData() {
        return this.pageData;
    }
};

// 代码编辑器管理模块
const CodeEditorManager = {
    codeEditor: null,
    isInitialized: false,

    async init() {
        if (this.isInitialized) {
            return;
        }

        try {
            if (window.SimpleCodeEditor) {
                this.codeEditor = new SimpleCodeEditor();
                await this.codeEditor.init();
                this.isInitialized = true;
            } else {
                // console.warn('SimpleCodeEditor 未加载，使用简单编辑器');
                this.isInitialized = true;
            }
        } catch (error) {
            // console.error('代码编辑器初始化失败:', error);
            this.isInitialized = true;
        }
    },

    async createEditor(containerId, code, language = 'javascript') {
        // 确保容器存在
        const container = document.getElementById(containerId);
        if (!container) {
            // console.error(`容器 ${containerId} 不存在`);
            return;
        }

        // 清空容器
        container.innerHTML = '';

        if (this.codeEditor && this.isInitialized) {
            try {
                await this.codeEditor.createEditor(containerId, code || '');
            } catch (error) {
                // console.error(`代码编辑器 ${containerId} 创建失败:`, error);
                this.createSimpleEditor(containerId, code, language);
            }
        } else {
            this.createSimpleEditor(containerId, code, language);
        }
    },

    updateEditor(containerId, newCode) {
        if (this.codeEditor && this.isInitialized) {
            try {
                this.codeEditor.updateEditor(containerId, newCode);
            } catch (error) {
                // console.error('更新编辑器内容失败:', error);
                this.updateSimpleEditor(containerId, newCode);
            }
        } else {
            this.updateSimpleEditor(containerId, newCode);
        }
    },

    createSimpleEditor(containerId, code, language = 'javascript') {
        const container = document.getElementById(containerId);
        if (container) {
            // 根据语言设置不同的样式
            const languageClass = this.getLanguageClass(language);

            container.innerHTML = `
                <div class="simple-editor ${languageClass}" style="
                    background: #1e1e1e;
                    border: 1px solid #333;
                    border-radius: 6px;
                    padding: 0;
                    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                    font-size: 14px;
                    line-height: 1.5;
                    overflow: hidden;
                    position: relative;
                ">
                    <div class="editor-header" style="
                        background: #2d2d30;
                        padding: 8px 15px;
                        border-bottom: 1px solid #333;
                        color: #ccc;
                        font-size: 12px;
                    ">
                        ${this.getLanguageName(language)}
                    </div>
                    <pre style="
                        margin: 0;
                        padding: 15px;
                        color: #d4d4d4;
                        overflow-x: auto;
                        white-space: pre-wrap;
                        word-wrap: break-word;
                        max-height: 400px;
                        overflow-y: auto;
                        background: #1e1e1e;
                    "><code>${this.escapeHtml(code || '')}</code></pre>
                </div>
            `;
        }
    },

    updateSimpleEditor(containerId, newCode) {
        const container = document.getElementById(containerId);
        if (container) {
            const codeElement = container.querySelector('code');
            if (codeElement) {
                codeElement.textContent = newCode || '';
            }
        }
    },

    getLanguageClass(language) {
        const languageMap = {
            1: 'cpp',
            2: 'python',
            3: 'javascript',
            4: 'java'
        };
        return languageMap[language] || 'javascript';
    },

    getLanguageName(language) {
        const languageMap = {
            1: 'C++',
            2: 'Python',
            3: 'JavaScript',
            4: 'Java'
        };
        return languageMap[language] || 'JavaScript';
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// DOM更新模块
const DOMUpdater = {
    // 存储模块的显示状态
    moduleDisplayState: {
        ratingSection: null, // null表示未设置，true表示应该显示，false表示应该隐藏
        reviewSection: null,
        workIntro: null, // 作品介绍模块显示状态
        workOperation: null // 操作说明模块显示状态
    },

    // 设置模块显示状态
    setModuleDisplayState(moduleName, shouldShow) {
        this.moduleDisplayState[moduleName] = shouldShow;
    },

    // 获取模块显示状态
    getModuleDisplayState(moduleName) {
        return this.moduleDisplayState[moduleName];
    },

    // 应用模块显示状态
    applyModuleDisplayState(moduleName) {
        const shouldShow = this.moduleDisplayState[moduleName];
        if (shouldShow === null) {
            return;
        }

        const element = document.querySelector(`.${moduleName}`);
        if (element) {
            element.style.display = shouldShow ? 'block' : 'none';
        }
    },

    updateElement(selector, content) {
        const element = document.querySelector(selector);
        if (element) {
            element.innerHTML = content;
        } else {
            // console.warn(`元素未找到: ${selector}`);
        }
    },

    updateProjectInfo(data) {

        // 处理不同的数据结构
        let tchWork, tchInfo, subject_code;

        if (data && data.content) {
            // 新数据结构
            tchWork = data.content.tchWork;
            tchInfo = data.content.tchInfo;
            subject_code = data.content.subject_code;
        } else if (data && data.tchWork) {
            // 旧数据结构
            tchWork = data.tchWork;
            tchInfo = data.tchInfo;
            subject_code = data.subject_code;
        } else if (data && data.work) {
            // 没有stuTchPlanId时的数据结构
            tchWork = data.work;
            tchInfo = data.tchInfo;
            subject_code = data.subject_code;
        } else {
            // console.error('无效的数据结构:', data);
            return;
        }

        // 更新项目标题
        if (tchWork && tchWork.title) {
            this.updateElement(CONFIG.selectors.projectTitle, tchWork.title);
        } else {
            // console.warn('标题数据不存在');
            // 设置默认标题
            this.updateElement(CONFIG.selectors.projectTitle, '作品标题');
        }

        // 更新作品信息
        if (tchWork) {
            // 更新作品图片
            if (tchWork.covers) {
                const workImgElement = document.querySelector(CONFIG.selectors.workImg);
                if (workImgElement) {
                    workImgElement.src = tchWork.covers;
                    workImgElement.alt = tchWork.title || '作品图片';
                }
            }

            // 更新作品标题
            if (tchWork.title) {
                this.updateElement(CONFIG.selectors.workTitleText, tchWork.title);
            }

            // 更新作品类型
            if (tchWork.work_type !== undefined) {
                let workTypeText = '';
                if (tchWork.work_type === 1) {
                    workTypeText = '课堂';
                } else if (tchWork.work_type === 2) {
                    workTypeText = '作业';
                }

                if (workTypeText) {
                    this.updateElement(CONFIG.selectors.workType, workTypeText);
                }
            }
        }

        // 更新教师信息
        if (tchInfo && tchInfo.realname) {
            const teacherInfoElement = document.querySelector(CONFIG.selectors.teacherInfo);
            if (teacherInfoElement) {
                const bElement = teacherInfoElement.querySelector('b');
                if (bElement) {
                    bElement.textContent = tchInfo.realname;
                }
            }
        } else {
            // console.warn('教师信息不存在');
            // 清空教师信息显示
            const teacherInfoElement = document.querySelector(CONFIG.selectors.teacherInfo);
            if (teacherInfoElement) {
                const bElement = teacherInfoElement.querySelector('b');
                if (bElement) {
                    bElement.textContent = '';
                }
            }
        }

        // 更新时间信息
        if (tchWork && tchWork.update_time) {
            const publishTimeElement = document.querySelector(CONFIG.selectors.publishTime);
            if (publishTimeElement) {
                const bElement = publishTimeElement.querySelector('b');
                if (bElement) {
                    bElement.textContent = tchWork.update_time;
                }
            }

            // 更新workPublishTime信息
            this.updateElement(CONFIG.selectors.workPublishTime, tchWork.update_time);
        } else {
            // console.warn('时间信息不存在');
            // 清空时间信息显示
            const publishTimeElement = document.querySelector(CONFIG.selectors.publishTime);
            if (publishTimeElement) {
                const bElement = publishTimeElement.querySelector('b');
                if (bElement) {
                    bElement.textContent = '';
                }
            }
            this.updateElement(CONFIG.selectors.workPublishTime, '');
        }

        // 更新学生信息
        if (tchWork && tchWork.name) {
            const studentInfoElement = document.querySelector(CONFIG.selectors.studentInfo);
            if (studentInfoElement) {
                const bElement = studentInfoElement.querySelector('b');
                if (bElement) {
                    bElement.textContent = tchWork.name;
                }
            }

            // 更新workStudentName信息
            this.updateElement(CONFIG.selectors.workStudentName, tchWork.name);
        } else {
            // console.warn('学生信息不存在');
            // 清空学生信息显示
            const studentInfoElement = document.querySelector(CONFIG.selectors.studentInfo);
            if (studentInfoElement) {
                const bElement = studentInfoElement.querySelector('b');
                if (bElement) {
                    bElement.textContent = '';
                }
            }
            this.updateElement(CONFIG.selectors.workStudentName, '');
        }

        // 更新评语 - 使用tchWork.remark字段
        if (tchWork && tchWork.remark) {
            this.updateElement(CONFIG.selectors.reviewText, marked.parse(tchWork.remark));
            // 设置评语模块显示状态为显示
            this.setModuleDisplayState('review-section', true);
        } else {
            // console.warn('评语信息不存在');
            // 设置评语模块显示状态为隐藏
            this.setModuleDisplayState('review-section', false);
        }

        // 更新作品介绍 - 使用tchWork.abstract字段
        if (tchWork && tchWork.abstract) {
            this.updateElement(CONFIG.selectors.introText, tchWork.abstract);
            // 设置作品介绍模块显示状态为显示
            this.setModuleDisplayState('work-intro', true);
        } else {
            // console.warn('作品介绍信息不存在');
            // 设置作品介绍模块显示状态为隐藏
            this.setModuleDisplayState('work-intro', false);
        }

        // 更新操作说明 - 使用tchWork.explain字段
        if (tchWork && tchWork.explain) {
            this.updateElement(CONFIG.selectors.operationText, tchWork.explain);
            // 设置操作说明模块显示状态为显示
            this.setModuleDisplayState('work-operation', true);
        } else {
            // console.warn('操作说明信息不存在');
            // 设置操作说明模块显示状态为隐藏
            this.setModuleDisplayState('work-operation', false);
        }

        // 对于SC作品（subjectCode等于2），根据数据内容决定是否显示作品介绍和操作说明模块
        if (subject_code === 2) {
            // 模块显示状态已在上面设置，这里只需要确保应用状态
        }

        // 更新星级评价 - 使用tchWork.markpoint字段
        this.updateRatingBasedOnMarkpoint(tchWork?.markpoint);

        // 处理代码数据
        this.handleCodeData({ tchWork, tchInfo, subject_code });
    },

    // 根据markpoint字段更新星级评价
    updateRatingBasedOnMarkpoint(markpoint) {
        let rating = 0;
        let hasRating = false;

        if (markpoint !== null && markpoint !== undefined && markpoint !== '') {
            // 如果markpoint存在且有效，直接使用该值
            rating = parseFloat(markpoint);

            // 确保评分在1-5范围内
            rating = Math.min(5, Math.max(0, rating));

            hasRating = true;
        } else {
        }

        if (hasRating) {
            // 有评分时设置模块显示状态为显示并更新内容
            this.setModuleDisplayState('rating-section', true);
            // 生成星级评价HTML
            const ratingHTML = CONFIG.templates.rating(rating);
            this.updateElement(CONFIG.selectors.ratingStars, ratingHTML);
        } else {
            // 没有评分时设置模块显示状态为隐藏
            this.setModuleDisplayState('rating-section', false);
        }
    },

    handleCodeData(data) {

        // 使用CodeDataManager处理数据
        CodeDataManager.processCodeData(data);

        const codeData = CodeDataManager.getCodeData();

        // 根据内容类型显示不同的容器
        this.showAppropriateContainer(codeData);

        if (codeData.useIframe) {
            // 当subjectCode==1或2时，使用iframe显示
            this.createIframe(codeData.code);
        } else if (codeData.codeList && codeData.codeList.length > 0) {
            // 创建代码标签
            this.createCodeTags(codeData.codeList);

            // 初始化代码编辑器
            this.initCodeEditor(codeData);
        } else {
            // console.warn('没有找到代码数据');
        }
    },

    showAppropriateContainer(codeData) {
        // 获取所有容器
        const codeBox = document.querySelector(CONFIG.selectors.codeBox);
        const jrContainer = document.querySelector('.jr-container');
        const scContainer = document.querySelector('.sc-container');
        const imageContainer = document.querySelector(CONFIG.selectors.imageContainer);
        const workBox = document.querySelector(CONFIG.selectors.workBox);

        // 默认隐藏所有容器
        if (codeBox) codeBox.style.display = 'none';
        if (jrContainer) jrContainer.style.display = 'none';
        if (scContainer) scContainer.style.display = 'none';
        if (imageContainer) imageContainer.style.display = 'none';
        if (workBox) workBox.style.display = 'none'; // 隐藏work-box

        // 根据内容类型显示对应容器
        if (codeData.useIframe) {
            // 只有当subjectCode等于1或2时才显示work-box容器
            if (codeData.subjectCode === 1 || codeData.subjectCode === 2) {
                if (workBox) {
                    workBox.style.display = 'block';

                    // 设置初始高度为 100vw（非全屏/非游戏运行状态）
                    workBox.style.height = '95vw';

                    // 根据subjectCode显示对应的iframe容器
                    if (codeData.subjectCode === 1) {
                        if (jrContainer) {
                            jrContainer.style.display = 'block';
                        }
                    } else if (codeData.subjectCode === 2) {
                        if (scContainer) {
                            scContainer.style.display = 'block';
                        }
                    }
                }
            } else {
            }
        } else if (codeData.codeList && codeData.codeList.length > 0) {
            // 显示代码编辑器容器
            if (codeBox) {
                codeBox.style.display = 'flex';
            }
        } else {
            // 显示默认图片容器
            if (imageContainer) {
                imageContainer.style.display = 'flex';
            }
        }

        // 移除最后的work-box显示逻辑，因为已经在上面处理了
        // if (workBox) {
        //     workBox.style.display = 'block';
        // }
    },

    createIframe(url) {

        const codeData = CodeDataManager.getCodeData();
        const subjectCode = codeData.subjectCode;

        if (subjectCode === 1) {
            // 设置JR iframe
            const jrIframe = document.querySelector('.jr-container iframe');
            if (jrIframe) {
                jrIframe.src = url;

                // 只有subjectCode等于1时才监听JR iframe中的全屏事件
                this.listenToIframeFullscreen(jrIframe);
            } else {
                // console.error('找不到JR iframe元素');
            }
        } else if (subjectCode === 2) {
            // 设置SC iframe
            const scIframe = document.querySelector('.sc-container iframe');
            if (scIframe) {
                scIframe.src = url;

                // subjectCode等于2时不执行全屏监听，但监听游戏开始和结束
                this.listenToScGameEvents(scIframe);
            } else {
                // console.error('找不到SC iframe元素');
            }
        } else {
            // console.error('未知的subjectCode:', subjectCode);
        }
    },

    // 监听iframe中的全屏事件
    listenToIframeFullscreen(iframe) {

        // 立即设置基础监听器（不依赖iframe内容）
        this.setupImmediateFullscreenListener(iframe);

        // 监听iframe的load事件
        iframe.addEventListener('load', () => {

            // 立即尝试设置监听器（不等待）
            this.setupFullscreenListener(iframe);
            this.setupJrFullscreenManager(iframe);

            // 延迟一点时间确保iframe内容完全加载，再次尝试设置
            setTimeout(() => {
                this.setupFullscreenListener(iframe);
                this.setupJrFullscreenManager(iframe);
            }, 2000);

            // 再延迟3秒，确保JR内容完全初始化
            setTimeout(() => {
                this.setupFullscreenListener(iframe);
                this.setupJrFullscreenManager(iframe);
            }, 5000);
        });
    },

    // 监听SC游戏事件
    listenToScGameEvents(iframe) {

        // 初始化SC游戏状态
        this.scGameState = 'stopped';

        // 监听iframe的load事件
        iframe.addEventListener('load', () => {

            // 延迟一点时间确保iframe内容完全加载
            setTimeout(() => {
                this.setupScGameListeners(iframe);
            }, 1000);
        });

        // 监听来自SC页面的消息
        window.addEventListener('message', (event) => {
            // 验证消息来源
            if (event.source === iframe.contentWindow) {

                if (event.data && event.data.type === 'scGameStart') {
                    this.handleScGameStart();
                } else if (event.data && event.data.type === 'scGameStop') {
                    this.handleScGameStop();
                } else if (event.data && event.data.type === 'scGameState') {
                    this.handleScGameStateChange(event.data.state);
                }
            }
        });
    },

    // 设置SC游戏监听器
    setupScGameListeners(iframe) {
        try {
            const iframeWindow = iframe.contentWindow;

            if (iframeWindow) {

                // 向SC页面发送监听请求
                iframeWindow.postMessage({
                    type: 'requestGameListeners',
                    source: 'lessonWork'
                }, '*');

                // 发送测试消息验证通信
                setTimeout(() => {
                    try {
                        iframeWindow.postMessage({
                            type: 'testMessage',
                            source: 'lessonWork',
                            timestamp: Date.now()
                        }, '*');
                    } catch (error) {
                        // console.warn('发送测试消息失败:', error);
                    }
                }, 2000);

                // 监听SC页面的游戏状态变化
                const checkScGameState = setInterval(() => {
                    try {
                        // 检查SC页面的游戏状态
                        if (iframeWindow.vm) {
                            // 如果VM存在，说明游戏已加载
                            clearInterval(checkScGameState);

                            // 监听VM的运行状态
                            this.monitorScVmState(iframeWindow.vm);
                        }
                    } catch (error) {
                        // 跨域访问可能失败，忽略错误
                    }
                }, 500);

                // 设置超时
                setTimeout(() => {
                    clearInterval(checkScGameState);
                }, 10000);
            }
        } catch (error) {
            // console.warn('设置SC游戏监听器失败:', error);
        }
    },

    // 监听SC VM状态
    monitorScVmState(vm) {
        try {

            // 监听VM的运行状态变化
            if (vm.runtime) {
                // 监听运行时状态
                const originalStart = vm.runtime.start;
                const originalStop = vm.runtime.stop;

                vm.runtime.start = function () {
                    // 向父页面发送游戏开始消息
                    window.parent.postMessage({
                        type: 'scGameStart',
                        timestamp: Date.now()
                    }, '*');
                    return originalStart.call(this);
                };

                vm.runtime.stop = function () {
                    // 向父页面发送游戏停止消息
                    window.parent.postMessage({
                        type: 'scGameStop',
                        timestamp: Date.now()
                    }, '*');
                    return originalStop.call(this);
                };
            }
        } catch (error) {
            // console.warn('监听SC VM状态失败:', error);
        }
    },

    // 处理SC游戏开始
    handleScGameStart() {

        // 检查是否为SC作品（subjectCode === 2）
        const codeData = CodeDataManager.getCodeData();
        if (codeData.subjectCode !== 2) {
            return;
        }

        // 防止重复处理
        if (this.scGameState === 'running') {
            return;
        }

        this.scGameState = 'running';

        // 显示游戏开始通知
        this.showFullscreenNotification('SC游戏已开始');

        // 可以在这里添加游戏开始时的自定义逻辑
        // 比如：隐藏其他UI元素、调整布局等
        this.handleScGameEnter();
    },

    // 处理SC游戏停止
    handleScGameStop() {

        // 检查是否为SC作品（subjectCode === 2）
        const codeData = CodeDataManager.getCodeData();
        if (codeData.subjectCode !== 2) {
            return;
        }

        // 防止重复处理
        if (this.scGameState === 'stopped') {
            return;
        }

        this.scGameState = 'stopped';

        // 显示游戏停止通知
        this.showFullscreenNotification('SC游戏已结束');

        // 可以在这里添加游戏停止时的自定义逻辑
        // 比如：恢复UI元素、调整布局等
        this.handleScGameExit();
    },

    // 处理SC游戏状态变化
    handleScGameStateChange(state) {

        // 检查是否为SC作品（subjectCode === 2）
        const codeData = CodeDataManager.getCodeData();
        if (codeData.subjectCode !== 2) {
            return;
        }

        if (state === 'running') {
            this.handleScGameStart();
        } else if (state === 'stopped') {
            this.handleScGameStop();
        }
    },

    // 处理SC游戏进入
    handleScGameEnter() {

        // 可以在这里添加游戏运行时的自定义逻辑
        // 比如：隐藏其他UI元素、调整布局等

        // 示例：隐藏项目信息区域
        const projectInfo = document.querySelector('.project-info');
        if (projectInfo) {
            projectInfo.style.display = 'none';
        }

        // 示例：隐藏评分区域
        const ratingSection = document.querySelector('.rating-section');
        if (ratingSection) {
            ratingSection.style.display = 'none';
        }

        // 示例：隐藏评语区域
        const reviewSection = document.querySelector('.review-section');
        if (reviewSection) {
            reviewSection.style.display = 'none';
        }

        // 示例：隐藏底部按钮
        const bottomButton = document.querySelector('.bottom-button');
        if (bottomButton) {
            bottomButton.style.display = 'none';
        }

        // 控制 .work-box 元素高度为 100vh
        const workBox = document.querySelector('.work-box');
        if (workBox) {
            workBox.style.height = '100vh';
        }

        // 调整SC iframe容器样式
        const scContainer = document.querySelector('.sc-container');
        if (scContainer) {
            scContainer.style.position = 'fixed';
            scContainer.style.top = '0';
            scContainer.style.left = '0';
            scContainer.style.width = '100vw';
            scContainer.style.height = '100vh';
            scContainer.style.zIndex = '9999';
            scContainer.style.backgroundColor = '#000';
        }
    },

    // 处理SC游戏退出
    handleScGameExit() {
        // alert('sc game exit')
        // 检查是否为webview模式
        // 恢复SC iframe容器样式
        const scContainer = document.querySelector('.sc-container');
        if (scContainer) {
            scContainer.style.position = '';
            scContainer.style.top = '';
            scContainer.style.left = '';
            scContainer.style.width = '';
            scContainer.style.height = '';
            scContainer.style.zIndex = '';
            scContainer.style.backgroundColor = '';
        }
        const mode = getUrlParam('mode');
        if (mode === 'webview') {
            // webview模式下，退出游戏后仍然隐藏所有其他元素
            PageController.ensureWebviewElementsHidden();
            return;
        }

        // 获取stuTchPlanId参数
        const stuTchPlanId = getUrlParam('stuTchPlanId');

        // 根据stuTchPlanId参数控制模块显示
        if (stuTchPlanId) {
            // 有stuTchPlanId参数时，显示课堂作品相关模块
            const projectInfo = document.querySelector('.project-info');
            if (projectInfo) {
                projectInfo.style.display = '';
                projectInfo.style.justifyContent = '';
            }

            // 根据数据驱动的显示状态显示星级评价、评语模块
            DOMUpdater.applyModuleDisplayState('rating-section');
            DOMUpdater.applyModuleDisplayState('review-section');

            // 显示底部按钮模块
            const bottomButton = document.querySelector('.bottom-button');
            if (bottomButton) bottomButton.style.display = 'block';

            // 隐藏作品介绍和操作说明模块
            const workIntro = document.querySelector('.work-intro');
            const workOperation = document.querySelector('.work-operation');
            // 检查作品介绍模块是否有数据，有数据才显示
            const workIntroShouldShow = this.getModuleDisplayState('work-intro');
            if (workIntro && workIntroShouldShow) {
                workIntro.style.display = 'block';
            } else if (workIntro) {
                workIntro.style.display = 'none';
            }

            // 检查操作说明模块是否有数据，有数据才显示
            const workOperationShouldShow = this.getModuleDisplayState('work-operation');
            if (workOperation && workOperationShouldShow) {
                workOperation.style.display = 'block';
            } else if (workOperation) {
                workOperation.style.display = 'none';
            }

        } else {
            // 没有stuTchPlanId参数时，显示普通作品相关模块
            const projectInfo = document.querySelector('.project-info');
            if (projectInfo) {
                projectInfo.style.display = 'flex';
                projectInfo.style.justifyContent = 'space-between';
            }

            // 隐藏星级评价、评语、底部按钮模块
            const ratingSection = document.querySelector('.rating-section');
            const reviewSection = document.querySelector('.review-section');
            const bottomButton = document.querySelector('.bottom-button');

            if (ratingSection) ratingSection.style.display = 'none';
            if (reviewSection) reviewSection.style.display = 'none';
            if (bottomButton) bottomButton.style.display = 'none';

            // 显示作品介绍和操作说明模块（根据数据状态决定是否显示）
            const workIntro = document.querySelector('.work-intro');
            const workOperation = document.querySelector('.work-operation');

            // 检查作品介绍模块是否有数据，有数据才显示
            const workIntroShouldShow = this.getModuleDisplayState('work-intro');
            if (workIntro && workIntroShouldShow) {
                workIntro.style.display = 'block';
            } else if (workIntro) {
                workIntro.style.display = 'none';
            }

            // 检查操作说明模块是否有数据，有数据才显示
            const workOperationShouldShow = this.getModuleDisplayState('work-operation');
            if (workOperation && workOperationShouldShow) {
                workOperation.style.display = 'block';
            } else if (workOperation) {
                workOperation.style.display = 'none';
            }

        }

        // 控制 .work-box 元素高度为 100vw
        const workBox = document.querySelector('.work-box');
        if (workBox) {
            workBox.style.height = '95vw';
        }


    },

    // 立即设置基础全屏监听器（不依赖iframe内容）
    setupImmediateFullscreenListener(iframe) {

        // 监听iframe的message事件（跨域通信）
        window.addEventListener('message', (event) => {
            // 验证消息来源
            if (event.source === iframe.contentWindow) {

                if (event.data && event.data.type === 'fullscreen') {
                    this.handleIframeFullscreenMessage(event.data);
                } else if (event.data && event.data.type === 'jrFullscreenChange') {
                    this.handleJrFullscreenChange(event.data.isFullscreen);
                } else if (event.data && event.data.type === 'scGameStart') {
                    this.handleScGameStart();
                } else if (event.data && event.data.type === 'scGameStop') {
                    this.handleScGameStop();
                } else if (event.data && event.data.type === 'scGameState') {
                    this.handleScGameStateChange(event.data.state);
                } else {
                }
            } else {
            }
        });

        // 监听iframe的resize事件（可能表示全屏状态变化）
        iframe.addEventListener('resize', () => {
            // 延迟检查，避免频繁触发
            setTimeout(() => {
                this.checkIframeFullscreenState(iframe);
            }, 100);
        });

        // 监听iframe的focus/blur事件
        iframe.addEventListener('focus', () => {
        });

        iframe.addEventListener('blur', () => {
        });
    },

    // 检查iframe全屏状态
    checkIframeFullscreenState(iframe) {
        try {
            const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
            if (iframeDoc) {
                const isFullscreen = iframeDoc.fullscreenElement ||
                    iframeDoc.webkitFullscreenElement ||
                    iframeDoc.mozFullScreenElement ||
                    iframeDoc.msFullscreenElement;


                if (isFullscreen) {
                    this.handleJrFullscreenChange(true);
                } else {
                    this.handleJrFullscreenChange(false);
                }
            }
        } catch (error) {
            // console.warn('检查iframe全屏状态失败:', error);
        }
    },

    // 设置JR全屏管理器监听
    setupJrFullscreenManager(iframe) {
        try {
            const iframeWindow = iframe.contentWindow;

            if (iframeWindow) {

                // 立即检查一次
                if (iframeWindow.JrFullscreenManager) {

                    this.setupJrFullscreenListeners(iframeWindow);
                    return;
                }

                // 等待JrFullscreenManager加载完成，使用更快的检查频率
                const checkJrManager = setInterval(() => {
                    if (iframeWindow.JrFullscreenManager) {
                        clearInterval(checkJrManager);
                        this.setupJrFullscreenListeners(iframeWindow);
                    }
                }, 100); // 从500ms改为100ms，更快响应

                // 设置超时，避免无限等待
                setTimeout(() => {
                    clearInterval(checkJrManager);
                    // 超时后尝试其他监听方式
                    this.setupAlternativeFullscreenListeners(iframe);
                }, 5000); // 从10秒改为5秒

            }
        } catch (error) {
            // 失败后尝试其他监听方式
            this.setupAlternativeFullscreenListeners(iframe);
        }
    },

    // 设置JR全屏监听器
    setupJrFullscreenListeners(iframeWindow) {
        try {
            // 添加全屏状态变化监听器
            iframeWindow.JrFullscreenManager.addListener((isFullscreen) => {
                this.handleJrFullscreenChange(isFullscreen);
            });

            // 监听自定义全屏事件
            iframeWindow.addEventListener('jrFullscreenChange', (event) => {
                this.handleJrFullscreenChange(event.detail.isFullscreen);
            });

            // 获取初始状态
            const initialState = iframeWindow.JrFullscreenManager.getState();

            // 如果初始状态就是全屏，立即处理
            if (initialState) {
                this.handleJrFullscreenChange(true);
            }
        } catch (error) {
        }
    },

    // 设置备用的全屏监听方式
    setupAlternativeFullscreenListeners(iframe) {

        try {
            const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
            const iframeWindow = iframe.contentWindow;

            if (iframeDoc && iframeWindow) {
                // 监听iframe内的全屏变化事件
                iframeDoc.addEventListener('fullscreenchange', (e) => {
                    this.handleIframeFullscreenChange(iframe, iframeDoc);
                });

                // 兼容不同浏览器
                iframeDoc.addEventListener('webkitfullscreenchange', (e) => {
                    this.handleIframeFullscreenChange(iframe, iframeDoc);
                });

                iframeDoc.addEventListener('mozfullscreenchange', (e) => {
                    this.handleIframeFullscreenChange(iframe, iframeDoc);
                });

                iframeDoc.addEventListener('MSFullscreenChange', (e) => {
                    this.handleIframeFullscreenChange(iframe, iframeDoc);
                });

                // 监听iframe内的全局点击事件，检测全屏相关操作
                iframeDoc.addEventListener('click', (e) => {
                    const target = e.target;
                    if (target && (target.id === 'full' || target.className.includes('full') || target.className.includes('screen'))) {
                        this.handleIframeFullscreenClick(iframe);
                    }
                });

                // 定期检查全屏状态
                setInterval(() => {
                    this.checkIframeFullscreenState(iframe);
                }, 1000); // 每秒检查一次
            }
        } catch (error) {
        }
    },

    // 处理JR全屏状态变化
    handleJrFullscreenChange(isFullscreen) {

        // 检查是否为JR作品（subjectCode === 1）
        const codeData = CodeDataManager.getCodeData();
        if (codeData.subjectCode !== 1) {
            return;
        }

        // 更新全屏状态管理器
        FullscreenManager.setFullscreenState(isFullscreen, this.getCurrentIframe());

        if (isFullscreen) {
            this.showFullscreenNotification('JR作品已进入全屏模式');
            this.handleFullscreenEnter();
        } else {
            this.showFullscreenNotification('JR作品已退出全屏模式');
            this.handleFullscreenExit();
        }
    },

    // 获取当前iframe
    getCurrentIframe() {
        const codeData = CodeDataManager.getCodeData();
        if (codeData.subjectCode === 1) {
            return document.querySelector('.jr-container iframe');
        } else if (codeData.subjectCode === 2) {
            return document.querySelector('.sc-container iframe');
        }
        return null;
    },

    // 处理进入全屏
    handleFullscreenEnter() {

        // 检查是否为JR作品（subjectCode === 1）
        const codeData = CodeDataManager.getCodeData();
        if (codeData.subjectCode !== 1) {
            return;
        }

        // 可以在这里添加进入全屏时的自定义逻辑
        // 比如：隐藏其他UI元素、调整布局等

        // 示例：隐藏项目信息区域
        const projectInfo = document.querySelector('.project-info');
        if (projectInfo) {
            projectInfo.style.display = 'none';
        }

        // 示例：隐藏评分区域
        const ratingSection = document.querySelector('.rating-section');
        if (ratingSection) {
            ratingSection.style.display = 'none';
        }

        // 示例：隐藏评语区域
        const reviewSection = document.querySelector('.review-section');
        if (reviewSection) {
            reviewSection.style.display = 'none';
        }

        // 示例：隐藏底部按钮
        const bottomButton = document.querySelector('.bottom-button');
        if (bottomButton) {
            bottomButton.style.display = 'none';
        }

        // 控制 .work-box 元素高度为 100vh
        const workBox = document.querySelector('.work-box');
        if (workBox) {
            workBox.style.height = '100vh';
        }

        // 示例：调整iframe容器样式
        const jrContainer = document.querySelector('.jr-container');
        if (jrContainer) {
            jrContainer.style.position = 'fixed';
            jrContainer.style.top = '0';
            jrContainer.style.left = '0';
            jrContainer.style.width = '100vw';
            jrContainer.style.height = '100vh';
            jrContainer.style.zIndex = '9999';
            jrContainer.style.backgroundColor = '#000';
        }

        const scContainer = document.querySelector('.sc-container');
        if (scContainer) {
            scContainer.style.position = 'fixed';
            scContainer.style.top = '0';
            scContainer.style.left = '0';
            scContainer.style.width = '100vw';
            scContainer.style.height = '100vh';
            scContainer.style.zIndex = '9999';
            scContainer.style.backgroundColor = '#000';
        }
    },

    // 处理退出全屏
    handleFullscreenExit() {
        // alert('jr game exit')
        // 检查是否为JR作品（subjectCode === 1）或SC作品（subjectCode === 2）
        const codeData = CodeDataManager.getCodeData();
        if (codeData.subjectCode !== 1 && codeData.subjectCode !== 2) {
            return;
        }

        // 恢复iframe容器样式
        const jrContainer = document.querySelector('.jr-container');
        if (jrContainer) {
            jrContainer.style.position = '';
            jrContainer.style.top = '';
            jrContainer.style.left = '';
            jrContainer.style.width = '';
            jrContainer.style.height = '';
            jrContainer.style.zIndex = '';
            jrContainer.style.backgroundColor = '';
        }
        // 检查是否为webview模式
        const mode = getUrlParam('mode');
        if (mode === 'webview') {
            // webview模式下，退出全屏后仍然隐藏所有其他元素
            PageController.ensureWebviewElementsHidden();

            return;
        }

        // 获取stuTchPlanId参数
        const stuTchPlanId = getUrlParam('stuTchPlanId');
        // 根据stuTchPlanId参数控制模块显示
        if (stuTchPlanId) {
            // 有stuTchPlanId参数时，显示课堂作品相关模块
            const projectInfo = document.querySelector('.project-info');
            if (projectInfo) {
                projectInfo.style.display = '';
                projectInfo.style.justifyContent = '';
            }

            // 根据数据驱动的显示状态显示星级评价、评语模块
            DOMUpdater.applyModuleDisplayState('rating-section');
            DOMUpdater.applyModuleDisplayState('review-section');
            // 显示底部按钮模块
            const bottomButton = document.querySelector('.bottom-button');
            if (bottomButton) bottomButton.style.display = 'block';

            // 隐藏作品介绍和操作说明模块
            const workIntro = document.querySelector('.work-intro');
            const workOperation = document.querySelector('.work-operation');
            if (workIntro) workIntro.style.display = 'none';
            if (workOperation) workOperation.style.display = 'none';
        } else {
            // 没有stuTchPlanId参数时，显示普通作品相关模块
            const projectInfo = document.querySelector('.project-info');
            if (projectInfo) {
                projectInfo.style.display = 'flex';
                projectInfo.style.justifyContent = 'space-between';
            }

            // 隐藏星级评价、评语、底部按钮模块
            const ratingSection = document.querySelector('.rating-section');
            const reviewSection = document.querySelector('.review-section');
            const bottomButton = document.querySelector('.bottom-button');

            if (ratingSection) ratingSection.style.display = 'none';
            if (reviewSection) reviewSection.style.display = 'none';
            if (bottomButton) bottomButton.style.display = 'none';

            // 显示作品介绍和操作说明模块
            const workIntro = document.querySelector('.work-intro');
            const workOperation = document.querySelector('.work-operation');

            if (workIntro) workIntro.style.display = 'none';
            if (workOperation) workOperation.style.display = 'none';

        }
        // 控制 .work-box 元素高度为 95vw
        const workBox = document.querySelector('.work-box');
        if (workBox) {
            workBox.style.height = '95vw';
        }

    },

    // 设置iframe内的全屏监听器
    setupFullscreenListener(iframe) {
        try {
            const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
            const iframeWindow = iframe.contentWindow;

            if (iframeDoc && iframeWindow) {

                // 监听iframe内的全屏变化事件
                iframeDoc.addEventListener('fullscreenchange', (e) => {
                    this.handleIframeFullscreenChange(iframe, iframeDoc);
                });

                // 兼容不同浏览器
                iframeDoc.addEventListener('webkitfullscreenchange', (e) => {
                    this.handleIframeFullscreenChange(iframe, iframeDoc);
                });

                iframeDoc.addEventListener('mozfullscreenchange', (e) => {
                    this.handleIframeFullscreenChange(iframe, iframeDoc);
                });

                iframeDoc.addEventListener('MSFullscreenChange', (e) => {
                    this.handleIframeFullscreenChange(iframe, iframeDoc);
                });

                // 尝试监听iframe内的自定义事件
                iframeWindow.addEventListener('message', (event) => {
                    if (event.data && event.data.type === 'fullscreen') {
                        this.handleIframeFullscreenMessage(event.data);
                    }
                });

                // 尝试找到#full元素并监听点击事件
                const fullElement = iframeDoc.getElementById('full');
                if (fullElement) {
                    fullElement.addEventListener('click', (e) => {
                        this.handleIframeFullscreenClick(iframe);
                    });
                } else {
                    // 尝试监听其他可能触发全屏的元素
                    const fullscreenElements = iframeDoc.querySelectorAll('[class*="full"], [id*="full"], [class*="screen"], [id*="screen"]');
                    fullscreenElements.forEach(element => {
                        element.addEventListener('click', (e) => {
                            this.handleIframeFullscreenClick(iframe);
                        });
                    });
                }

                // 监听iframe内的全局点击事件，检测全屏相关操作
                iframeDoc.addEventListener('click', (e) => {
                    const target = e.target;
                    if (target && (target.id === 'full' || target.className.includes('full') || target.className.includes('screen'))) {
                        this.handleIframeFullscreenClick(iframe);
                    }
                });

            } else {
                // console.warn('无法访问iframe文档，可能是跨域限制');
            }
        } catch (error) {
        }
    },

    // 处理iframe内全屏状态变化
    handleIframeFullscreenChange(iframe, iframeDoc) {
        // 检查iframe内的全屏状态
        const isFullscreen = iframeDoc.fullscreenElement ||
            iframeDoc.webkitFullscreenElement ||
            iframeDoc.mozFullScreenElement ||
            iframeDoc.msFullscreenElement;

        if (isFullscreen) {
            this.showFullscreenNotification('JR作品已进入全屏模式');
        } else {
            this.showFullscreenNotification('JR作品已退出全屏模式');
        }
    },

    // 处理iframe内全屏按钮点击
    handleIframeFullscreenClick(iframe) {
        this.showFullscreenNotification('JR作品即将进入全屏模式');
    },

    // 处理iframe发送的全屏消息
    handleIframeFullscreenMessage(data) {
        if (data.action === 'enter') {
            this.showFullscreenNotification('JR作品已进入全屏模式');
        } else if (data.action === 'exit') {
            this.showFullscreenNotification('JR作品已退出全屏模式');
        }
    },

    // 显示全屏通知
    showFullscreenNotification(message) {
        // 创建通知元素
        // const notification = document.createElement('div');
        // notification.style.cssText = `
        //     position: fixed;
        //     top: 20px;
        //     left: 50%;
        //     transform: translateX(-50%);
        //     background: rgba(0, 0, 0, 0.8);
        //     color: white;
        //     padding: 10px 20px;
        //     border-radius: 5px;
        //     z-index: 9999;
        //     font-size: 14px;
        //     transition: opacity 0.3s;
        // `;
        // notification.textContent = message;

        // document.body.appendChild(notification);

        // // 3秒后自动移除
        // setTimeout(() => {
        //     notification.style.opacity = '0';
        //     setTimeout(() => {
        //         if (notification.parentNode) {
        //             notification.parentNode.removeChild(notification);
        //         }
        //     }, 300);
        // }, 3000);
    },

    createCodeTags(codeList) {
        const tagBox = document.querySelector(CONFIG.selectors.codeTagBox);
        if (!tagBox) {
            return;
        }

        let tagsHTML = '';
        codeList.forEach((item, index) => {
            const isActive = index === 0 ? 'active' : '';
            const label = item.label || item.oj_problem_title || `代码${index + 1}`;
            tagsHTML += `<span class="code-tag ${isActive}" data-id="${item.id}" data-index="${index}">${label}</span>`;
        });

        tagBox.innerHTML = tagsHTML;

        // 添加点击事件
        this.addCodeTagEvents();
    },

    addCodeTagEvents() {
        const tags = document.querySelectorAll('.code-tag');
        tags.forEach(tag => {
            tag.addEventListener('click', (e) => {
                const id = e.target.dataset.id;
                const index = parseInt(e.target.dataset.index);

                // 更新标签状态
                tags.forEach(t => t.classList.remove('active'));
                e.target.classList.add('active');

                // 更新代码数据
                const codeData = CodeDataManager.getCodeData();
                const selectedCode = codeData.codeList[index];
                if (selectedCode) {
                    CodeDataManager.updateCurrentCode(selectedCode.id, selectedCode.code);
                    CodeEditorManager.updateEditor('monaco_editor', selectedCode.code, selectedCode.language);
                }
            });
        });
    },

    async initCodeEditor(codeData) {

        if (codeData) {
            // 确保编辑器已初始化
            await CodeEditorManager.init();

            // 获取语言类型
            const language = codeData.codeList[0]?.language || 3; // 默认JavaScript

            await CodeEditorManager.createEditor('monaco_editor', codeData.code, language);
        }
    },

    updateAll(data) {
        this.updateProjectInfo(data);
        this.updateTagStyles(data);

        // 应用模块显示状态
        this.applyModuleDisplayState('rating-section');
        this.applyModuleDisplayState('review-section');
        this.applyModuleDisplayState('work-intro');
        this.applyModuleDisplayState('work-operation');

    },

    // 更新标签样式
    updateTagStyles(data) {

        // 获取标签容器
        const projectTag = document.querySelector('.project-tag');
        if (!projectTag) {
            return;
        }

        // 获取标签颜色配置
        const tagColors = [
            { color: '#58C680', backgroundColor: '#DCFCE7' },
            { color: '#E2D76A', backgroundColor: '#FEFCE8' },
            { color: '#EC6924', backgroundColor: '#FFDFCF' },
            { color: '#9E48EC', backgroundColor: '#EDD9FF' },
            { color: '#2463EB', backgroundColor: '#EAF0FF' },
            { color: '#E9B306', backgroundColor: '#FFF2C6' },
            { color: '#FC994A', backgroundColor: '#FFE0C8' },
            { color: '#17A34A', backgroundColor: '#DCFCE7' },
        ];

        // 获取标签列表
        let tagList = [];
        if (data && data.tchWork && data.tchWork.tagList) {
            // 处理tchWork.tagList的数据结构：[{workTagInfo:{name:'游戏'}}]
            tagList = data.tchWork.tagList.map(item => {
                if (item && item.workTagInfo && item.workTagInfo.name) {
                    return item.workTagInfo.name;
                }
                return null;
            }).filter(name => name !== null);
        } else if (data && data.work && data.work.tagList) {
            // 处理work.tagList的数据结构：[{workTagInfo:{name:'游戏'}}]
            tagList = data.work.tagList.map(item => {
                if (item && item.workTagInfo && item.workTagInfo.name) {
                    return item.workTagInfo.name;
                }
                return null;
            }).filter(name => name !== null);
        }

        if (tagList.length === 0) {
            projectTag.style.display = 'none';
            return;
        }

        // 显示标签容器
        projectTag.style.display = 'flex';

        // 清空现有标签
        projectTag.innerHTML = '';

        // 动态生成标签元素
        tagList.forEach((tagText, index) => {
            // 随机选择一个颜色配置
            const randomColorIndex = Math.floor(Math.random() * tagColors.length);
            const colorConfig = tagColors[randomColorIndex];

            // 创建标签元素
            const tagItem = document.createElement('div');
            tagItem.className = 'tag-item';
            tagItem.textContent = tagText;

            // 只应用颜色相关的样式，其他样式使用CSS
            tagItem.style.color = colorConfig.color;
            tagItem.style.backgroundColor = colorConfig.backgroundColor;

            // 添加到容器
            projectTag.appendChild(tagItem);

        });
    }
};

// 页面控制器
const PageController = {
    async init() {
        try {

            // 获取页面参数
            const params = {
                eduId: getUrlParam('eduId'),
                stuTchPlanId: getUrlParam('stuTchPlanId'),
                subjectCode: getUrlParam('subjectCode'),
                workId: getUrlParam('workId'),
                mode: getUrlParam('mode')
            };

            // 检查mode参数，如果mode=webview，只显示work-container
            if (params.mode === 'webview') {
                await this.showWebviewMode();
                return;
            }

            // 验证必要参数
            if (!params.workId || !params.subjectCode) {
                // 显示错误信息给用户
                this.showError('缺少必要参数，请检查URL');
                return;
            }

            // 根据stuTchPlanId参数控制.project-info内子元素的显示状态
            this.controlProjectInfoDisplay(params.stuTchPlanId);

            // 在非webview模式下隐藏.work-info模块
            const workInfo = document.querySelector('.work-info');
            if (workInfo) {
                workInfo.style.display = 'none';
            }

            // 获取数据
            const data = await DataManager.fetchData(params);

            // 更新页面
            DOMUpdater.updateAll(data);

            // 获取微信SDK签名
            getWxSDKSign(data);

        } catch (error) {
            // console.error("页面初始化失败:", error);
            this.showError('页面加载失败: ' + error.message);
        }
    },

    // 显示webview模式，只显示work-container
    async showWebviewMode() {
        // 隐藏除work-container外的所有元素
        this.ensureWebviewElementsHidden();

        // 确保work-container显示
        const workContainer = document.querySelector('.work-container');
        if (workContainer) {
            workContainer.style.display = 'block';
        }

        // 调整页面样式，让work-container占满整个视口
        const page = document.querySelector('.page');
        if (page) {
            page.style.padding = '0';
            page.style.margin = '0';
        }

        // 调整body样式
        document.body.style.margin = '0';
        document.body.style.padding = '0';

        // 在webview模式下也需要获取数据来显示作品内容
        try {
            const params = {
                eduId: getUrlParam('eduId'),
                stuTchPlanId: getUrlParam('stuTchPlanId'),
                subjectCode: getUrlParam('subjectCode'),
                workId: getUrlParam('workId'),
                mode: getUrlParam('mode')
            };

            // 验证必要参数
            if (!params.workId || !params.subjectCode) {
                console.warn('webview模式下缺少必要参数');
                return;
            }

            // 获取数据并更新work-container内容
            const data = await DataManager.fetchData(params);
            DOMUpdater.updateAll(data);

            // 在webview模式下，确保作品介绍和操作说明被隐藏
            this.ensureWebviewElementsHidden();
        } catch (error) {
            console.error('webview模式下数据加载失败:', error);
        }
    },

    // 确保webview模式下特定元素被隐藏
    ensureWebviewElementsHidden() {
        const elementsToHide = [
            '.project-title',
            '.project-info',
            '.project-tag',
            '.work-intro',
            '.work-operation',
            '.rating-section',
            '.review-section',
            '.bottom-button'
        ];

        elementsToHide.forEach(selector => {
            const element = document.querySelector(selector);
            if (element) {
                element.style.display = 'none';
            }
        });

        // 在webview模式下显示.work-info模块
        const workInfo = document.querySelector('.work-info');
        if (workInfo) {
            workInfo.style.display = 'flex';
        }
    },

    // 控制.project-info内子元素的显示状态
    controlProjectInfoDisplay(stuTchPlanId) {

        const projectInfo = document.querySelector('.project-info');
        if (!projectInfo) {
            return;
        }

        // 获取所有.info-item和.project-info-item元素
        const infoItems = projectInfo.querySelectorAll('.info-item');
        const workInfoItems = projectInfo.querySelectorAll('.project-info-item');

        // 获取其他模块元素
        const ratingSection = document.querySelector('.rating-section');
        const reviewSection = document.querySelector('.review-section');
        const bottomButton = document.querySelector('.bottom-button');
        const workIntro = document.querySelector('.work-intro');
        const workOperation = document.querySelector('.work-operation');

        if (stuTchPlanId) {
            // 如果有stuTchPlanId参数，显示.info-item，隐藏.project-info-item
            infoItems.forEach(item => {
                item.style.display = 'flex';
            });
            workInfoItems.forEach(item => {
                item.style.display = 'none';
            });
            // 保持.project-info的默认样式
            projectInfo.style.display = '';
            projectInfo.style.justifyContent = '';

            // 根据数据驱动的显示状态显示星级评价、评语模块
            DOMUpdater.applyModuleDisplayState('rating-section');
            DOMUpdater.applyModuleDisplayState('review-section');

            // 显示底部按钮模块
            if (bottomButton) bottomButton.style.display = 'block';

            // 对于SC作品（subjectCode等于2），作品介绍和操作说明模块的显示由数据驱动
            // 对于其他作品，隐藏作品介绍和操作说明模块
            const subjectCode = getUrlParam('subjectCode');
            if (Number(subjectCode) === 2) {
                // SC作品：应用数据驱动的显示状态
                DOMUpdater.applyModuleDisplayState('work-intro');
                DOMUpdater.applyModuleDisplayState('work-operation');
            } else {
                // 非SC作品：隐藏作品介绍和操作说明模块
                if (workIntro) workIntro.style.display = 'none';
                if (workOperation) workOperation.style.display = 'none';
            }

        } else {
            // 如果没有stuTchPlanId参数，隐藏.info-item，显示.project-info-item
            infoItems.forEach(item => {
                item.style.display = 'none';
            });
            workInfoItems.forEach(item => {
                item.style.display = 'flex';
            });
            // 设置.project-info的样式为display:flex;justify-content:space-between
            projectInfo.style.display = 'flex';
            projectInfo.style.justifyContent = 'space-between';

            // 隐藏星级评价、评语、底部按钮模块
            if (ratingSection) ratingSection.style.display = 'none';
            if (reviewSection) reviewSection.style.display = 'none';
            if (bottomButton) bottomButton.style.display = 'none';

            // SC作品（subjectCode等于2）显示作品介绍和操作说明模块
            const subjectCode = getUrlParam('subjectCode');
            if (Number(subjectCode) === 2) {
                // 当subjectCode等于2时，无论有没有stuTchPlanId参数，都渲染这两个模块
                // 具体的显示/隐藏逻辑由数据驱动（在updateProjectInfo中设置）
                // 应用数据驱动的显示状态
                DOMUpdater.applyModuleDisplayState('work-intro');
                DOMUpdater.applyModuleDisplayState('work-operation');
            } else {
                // 非SC作品隐藏作品介绍和操作说明模块
                if (workIntro) workIntro.style.display = 'none';
                if (workOperation) workOperation.style.display = 'none';
            }

        }
    },

    showError(message) {
        // 在页面上显示错误信息
        const errorDiv = document.createElement('div');
        errorDiv.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #ff4444;
            color: white;
            padding: 20px;
            border-radius: 8px;
            z-index: 9999;
            max-width: 80%;
            text-align: center;
        `;
        errorDiv.textContent = message;
        document.body.appendChild(errorDiv);

        // 3秒后自动移除
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.parentNode.removeChild(errorDiv);
            }
        }, 3000);
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    PageController.init();

    // 初始化全屏监听器
    initFullscreenListeners();

    // 绑定CTA按钮点击事件
    bindCtaButtonEvent();
});

// 绑定CTA按钮点击事件
function bindCtaButtonEvent() {
    const ctaButton = document.querySelector('.cta-button');
    if (ctaButton) {
        ctaButton.addEventListener('click', handleCtaButtonClick);
    }
}

// 处理CTA按钮点击事件
function handleCtaButtonClick() {

    // 获取当前页面数据
    const pageData = DataManager.getData();
    if (!pageData) {
        showMessage('页面数据加载中，请稍后再试');
        return;
    }

    // 获取tchInfo数据
    let tchInfo = null;
    if (pageData.content && pageData.content.tchInfo) {
        tchInfo = pageData.content.tchInfo;
    } else if (pageData.tchInfo) {
        tchInfo = pageData.tchInfo;
    }

    // 检查card_img_url是否有值
    if (tchInfo && tchInfo.card_img_url) {
        showCardImageModal(tchInfo.card_img_url);
    } else {
        // showMessage('老师未上传名片');
        showMessage('点击客户端头像，进入个人资料，上传微信名片');
    }
}

// 显示名片图片弹框
function showCardImageModal(imageUrl) {
    // 创建模态框容器
    const modal = document.createElement('div');
    modal.className = 'card-image-modal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.4);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 10000;
        cursor: pointer;
        backdrop-filter: blur(2px);
    `;

    // 创建图片容器
    const imageContainer = document.createElement('div');
    imageContainer.style.cssText = `
        max-width: 90%;
        max-height: 90%;
        position: relative;
        cursor: default;
        background: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
    `;

    // 创建图片元素
    const img = document.createElement('img');
    img.src = imageUrl;
    img.style.cssText = `
        width: 100%;
        height: 100%;
        object-fit: contain;
        border-radius: 8px;
        display: block;
    `;

    // 创建关闭按钮
    const closeButton = document.createElement('div');
    closeButton.innerHTML = '×';
    closeButton.style.cssText = `
        position: absolute;
        top: -15px;
        right: -15px;
        width: 36px;
        height: 36px;
        background: #ff4757;
        color: white;
        border-radius: 50%;
        display: flex;
        justify-content: center;
        align-items: center;
        font-size: 24px;
        font-weight: bold;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 4px 12px rgba(255, 71, 87, 0.3);
        border: 2px solid white;
    `;

    // 添加关闭按钮悬停效果
    closeButton.addEventListener('mouseenter', () => {
        closeButton.style.background = '#ff3742';
        closeButton.style.transform = 'scale(1.1)';
        closeButton.style.boxShadow = '0 6px 16px rgba(255, 71, 87, 0.4)';
    });

    closeButton.addEventListener('mouseleave', () => {
        closeButton.style.background = '#ff4757';
        closeButton.style.transform = 'scale(1)';
        closeButton.style.boxShadow = '0 4px 12px rgba(255, 71, 87, 0.3)';
    });

    // 组装模态框
    imageContainer.appendChild(img);
    imageContainer.appendChild(closeButton);
    modal.appendChild(imageContainer);

    // 添加到页面
    document.body.appendChild(modal);

    // 绑定关闭事件
    const closeModal = () => {
        if (modal.parentNode) {
            modal.parentNode.removeChild(modal);
        }
    };

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeModal();
        }
    });

    closeButton.addEventListener('click', closeModal);

    // 添加ESC键关闭功能
    const handleEscKey = (e) => {
        if (e.key === 'Escape') {
            closeModal();
            document.removeEventListener('keydown', handleEscKey);
        }
    };
    document.addEventListener('keydown', handleEscKey);

}

// 显示消息提示
function showMessage(message) {
    // 创建消息提示元素
    const messageDiv = document.createElement('div');
    messageDiv.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: rgba(0, 0, 0, 0.8);
        color: white;
        padding: 15px 25px;
        border-radius: 8px;
        font-size: 16px;
        z-index: 10000;
        max-width: 80%;
        text-align: center;
        animation: fadeInOut 3s ease-in-out;
    `;

    // 添加动画样式
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeInOut {
            0% { opacity: 0; transform: translate(-50%, -50%) scale(0.8); }
            20% { opacity: 1; transform: translate(-50%, -50%) scale(1); }
            80% { opacity: 1; transform: translate(-50%, -50%) scale(1); }
            100% { opacity: 0; transform: translate(-50%, -50%) scale(0.8); }
        }
    `;
    document.head.appendChild(style);

    messageDiv.textContent = message;
    document.body.appendChild(messageDiv);

    // 3秒后自动移除
    setTimeout(() => {
        if (messageDiv.parentNode) {
            messageDiv.parentNode.removeChild(messageDiv);
        }
        if (style.parentNode) {
            style.parentNode.removeChild(style);
        }
    }, 3000);

}

// 初始化全屏监听器
function initFullscreenListeners() {

    // 添加全屏状态变化监听器
    FullscreenManager.addListener((isFullscreen, iframe) => {

        // 可以在这里添加页面级别的全屏处理逻辑
        if (isFullscreen) {
            // 进入全屏时的页面级处理
            document.body.style.overflow = 'hidden';
        } else {
            // 退出全屏时的页面级处理
            document.body.style.overflow = '';
        }
    });

    // 监听页面级别的全屏事件（作为备用）
    document.addEventListener('fullscreenchange', handlePageFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handlePageFullscreenChange);
    document.addEventListener('mozfullscreenchange', handlePageFullscreenChange);
    document.addEventListener('MSFullscreenChange', handlePageFullscreenChange);
}

// 处理页面级别的全屏变化
function handlePageFullscreenChange(event) {
    const isFullscreen = document.fullscreenElement ||
        document.webkitFullscreenElement ||
        document.mozFullScreenElement ||
        document.msFullscreenElement;

    // 如果页面进入全屏，但我们的iframe没有全屏，则同步状态
    if (isFullscreen && !FullscreenManager.getState()) {
        FullscreenManager.setFullscreenState(true);
    }
}

// JSSDK不能在页面初始化的时候就调用，没授权的时候调用会报congig:promision dnied错误；
// 并且如果要设置自定义分享的时候，不能带着从https://open.weixin.qq.com/connect/oauth2/authorize 授权后的url中的code，否则会报错；
// 获取微信SDK签名
const getWxSDKSign = (data) => {
    const { tchWork } = data
    return new Promise(resolve => {
        window.axios.get(`/api/wechat/get/JSSDK/sign`, {
            params: {
                url: location.href.split("#")[0],
            }
        }).then(response => {
            const res = response.data.content
            // appid.value = res.appId;
            resolve(res)
            window.wx.config({
                debug: location.origin === 'https://steam.fun' ? false : false, //调试的时候打开 
                appId: res.appId,
                timestamp: res.timestamp,
                nonceStr: res.nonceStr,
                signature: res.signature,
                jsApiList: [
                    "checkJsApi",
                    "onMenuShareTimeline",
                    "onMenuShareAppMessage",
                    "onMenuShareQQ",
                ],
            });
            window.wx.ready(() => {
                const shareData = {
                    // title: shareTitle.value,
                    title: `${tchWork.title}-${tchWork.name}-${tchWork.schoolName}`,
                    desc: `编程达人${tchWork.name}创作了一个很棒的编程作品,快来体验一下吧!`,
                    link: location.href.split("#")[0],
                    imgUrl: tchWork.covers,
                    success: function (shareRes) {
                        // alert(JSON.stringify(shareRes))
                    }
                };
                window.wx.onMenuShareAppMessage(shareData);
                window.wx.onMenuShareTimeline(shareData);
                window.wx.onMenuShareQQ(shareData);
            });
            window.wx.error((err) => {
                // console.log('wx error...', err)
                // if (process && process.env.NODE_ENV === "development") {
                // alert(err.errMsg); // 正式环境记得关闭啊！！！！
                // }
            });
        })
    })
}

// 暴露到全局，供其他脚本使用
window.CodeEditorManager = CodeEditorManager;
window.CodeDataManager = CodeDataManager;
window.FullscreenManager = FullscreenManager;
window.DOMUpdater = DOMUpdater;