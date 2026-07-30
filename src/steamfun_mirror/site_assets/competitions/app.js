// 全局变量
let typingText = '';
let typingIndex = 0;
let isTyping = false;

// 打字效果文本数组
const typingTexts = [
    '编程创新',
    '机器人竞赛',
    '科技特长生',
    '创新未来'
];

// 比赛详情数据
const competitionDetails = {
    noip: {
        title: 'NOIP信息学奥林匹克竞赛',
        description: '全国青少年信息学奥林匹克联赛（NOIP）是目前国内面向中学生的水平最高、规模最大的计算机竞赛。',
        process: [
            '1. 学校推荐或个人报名',
            '2. 参加初赛（笔试）',
            '3. 通过初赛进入复赛',
            '4. 复赛（上机编程）',
            '5. 根据成绩评定等级'
        ],
        benefits: [
            '省一等奖可直接保送知名大学',
            '省二等奖享受自主招生优惠',
            '提升逻辑思维和编程能力',
            '为将来从事IT行业奠定基础'
        ],
        website: 'http://www.noi.cn',
        contact: '湖北省计算机学会 027-87328115'
    },
    wrc: {
        title: '世界机器人大赛(WRC)',
        description: '世界机器人大赛是全球规模最大、影响力最广的机器人赛事，被誉为机器人界的"奥林匹克"。',
        process: [
            '1. 组建3-5人团队',
            '2. 选择参赛项目类别',
            '3. 设计制作机器人',
            '4. 参加地区选拔赛',
            '5. 优胜者晋级全国总决赛'
        ],
        benefits: [
            '培养团队协作能力',
            '提升工程设计思维',
            '锻炼动手实践能力',
            '获得科技特长生认证'
        ],
        website: 'http://www.worldrobotconference.com',
        contact: '宜昌市机器人协会 0717-6555888'
    },
    literacy: {
        title: '全国中小学信息素养大赛',
        description: '以"实践、探索、创新"为主题，旨在提升学生数字化学习与创新能力的综合性竞赛。',
        process: [
            '1. 在线注册报名',
            '2. 选择参赛组别和项目',
            '3. 提交参赛作品',
            '4. 专家在线评审',
            '5. 公布获奖名单'
        ],
        benefits: [
            '提升信息技术应用能力',
            '培养数字时代核心素养',
            '增强创新实践能力',
            '获得权威认证证书'
        ],
        website: 'http://www.wlxzz.com',
        contact: '宜昌市电教馆 0717-6441788'
    },
    computer: {
        title: '全国中小学电脑制作活动',
        description: '运用信息技术手段设计、创作数字化作品，培养学生创新精神和实践能力的综合活动。',
        process: [
            '1. 了解活动规则和要求',
            '2. 选择创作类别',
            '3. 独立设计制作作品',
            '4. 提交作品参加评选',
            '5. 优秀作品推荐上级评选'
        ],
        benefits: [
            '培养数字创作能力',
            '提升艺术设计素养',
            '锻炼创新思维',
            '展示个人才华'
        ],
        website: 'http://www.huodong2000.com.cn',
        contact: '宜昌市科协 0717-6445566'
    },
    innovation: {
        title: '全国青少年科技创新大赛',
        description: '由中国科协、教育部等主办的面向在校中小学生开展的具有示范性和导向性的科技教育活动。',
        process: [
            '1. 学校组织推荐报名',
            '2. 完成科技创新项目',
            '3. 参加地区初评选拔',
            '4. 省级复评和终评',
            '5. 优秀项目推荐全国赛'
        ],
        benefits: [
            '培养科学研究兴趣',
            '提升创新实践能力',
            '获得科技特长生认证',
            '优秀项目可申请专利'
        ],
        website: 'http://castic.xiaoxiaotong.org',
        contact: '湖北省科协青少部 027-87832039'
    },
    bluecup: {
        title: '蓝桥杯程序设计大赛',
        description: '由工业和信息化部人才交流中心主办的全国性软件和信息技术专业人才大赛。',
        process: [
            '1. 在线注册报名',
            '2. 选择参赛组别和语言',
            '3. 参加省级选拔赛',
            '4. 优胜者晋级全国总决赛',
            '5. 获奖证书和奖励'
        ],
        benefits: [
            '提升编程算法能力',
            '获得权威认证证书',
            '优秀选手推荐就业',
            '增强逻辑思维能力'
        ],
        website: 'http://www.lanqiao.cn',
        contact: '蓝桥杯湖北赛区 027-87654321'
    },
    vex: {
        title: 'VEX机器人世界锦标赛',
        description: 'VEX机器人竞赛是全球最大的机器人竞赛项目，旨在通过机器人竞赛培养学生的STEAM技能。',
        process: [
            '1. 组建3-5人参赛队伍',
            '2. 学习VEX编程和搭建',
            '3. 参加地区选拔赛',
            '4. 获得世锦赛参赛资格',
            '5. 参加VEX世界锦标赛'
        ],
        benefits: [
            '培养工程设计思维',
            '提升团队协作能力',
            '掌握机器人技术',
            '获得国际竞赛经验'
        ],
        website: 'http://www.vexrobotics.com',
        contact: 'VEX中国区 021-12345678'
    },
    frc: {
        title: 'FRC机器人竞赛',
        description: 'FIRST机器人竞赛是面向高中生的国际性机器人竞赛，被誉为"机器人界的奥林匹克"。',
        process: [
            '1. 注册FRC参赛队伍',
            '2. 获得比赛套件和规则',
            '3. 6周设计制作机器人',
            '4. 参加地区赛事',
            '5. 优胜队伍晋级世界赛'
        ],
        benefits: [
            '体验真实工程项目',
            '培养创新解决问题能力',
            '学习先进制造技术',
            '获得顶尖大学认可'
        ],
        website: 'http://www.firstinspires.org',
        contact: 'FIRST中国 010-87654321'
    },
    roborave: {
        title: 'RoboRAVE国际机器人大赛',
        description: 'RoboRAVE是一项面向青少年的国际机器人竞赛，旨在通过机器人竞赛培养学生的创新思维和团队合作精神。',
        process: [
            '1. 团队组建（2-4人）',
            '2. 选择挑战项目',
            '3. 设计搭建机器人',
            '4. 参加地区预选赛',
            '5. 优胜队伍参加全国总决赛'
        ],
        benefits: [
            '培养工程设计思维',
            '提升团队协作能力',
            '锻炼解决问题能力',
            '获得国际竞赛经验'
        ],
        website: 'http://www.roborave.org',
        contact: '宜昌市机器人协会 0717-6555888'
    },
    maker: {
        title: '全国青少年创客大赛',
        description: '以"发现、创造、分享"为主题，鼓励青少年利用数字化工具进行创意设计和智能制造。',
        process: [
            '1. 创意构思和方案设计',
            '2. 选择制作工具和材料',
            '3. 完成作品制作',
            '4. 提交作品和说明文档',
            '5. 参加现场答辩展示'
        ],
        benefits: [
            '培养创新设计思维',
            '掌握数字化制造技能',
            '提升动手实践能力',
            '激发创业创新精神'
        ],
        website: 'http://www.qsn365.com',
        contact: '宜昌市科技馆 0717-6222333'
    },
    ai: {
        title: '全国中小学人工智能大赛',
        description: '面向中小学生的人工智能教育竞赛，旨在普及人工智能知识，培养人工智能思维。',
        process: [
            '1. 学习人工智能基础知识',
            '2. 选择参赛项目类别',
            '3. 设计AI应用方案',
            '4. 编程实现AI功能',
            '5. 提交作品参加评选'
        ],
        benefits: [
            '掌握AI核心概念',
            '培养算法思维',
            '提升编程技能',
            '了解前沿科技'
        ],
        website: 'http://www.aidaai.com',
        contact: '宜昌市人工智能学会 0717-6333444'
    },
    iot: {
        title: '全国物联网设计竞赛',
        description: '物联网技术应用与创新设计竞赛，培养学生对物联网系统的理解和应用能力。',
        process: [
            '1. 学习物联网技术基础',
            '2. 确定应用场景和需求',
            '3. 设计物联网系统架构',
            '4. 开发硬件和软件部分',
            '5. 系统集成和测试验证'
        ],
        benefits: [
            '掌握物联网核心技术',
            '培养系统设计能力',
            '提升工程实践技能',
            '了解智能化应用'
        ],
        website: 'http://www.iotcontest.org',
        contact: '宜昌市电子信息协会 0717-6444555'
    }
};

// DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    // 记录页面访问
    recordPageVisit();
});

// 初始化应用
function initializeApp() {
    setupNavigation();
    setupTypingEffect();
    setupScrollEffects();
    setupLazyLoading();
    setupLoadMore();
    setupChatWidget();
    setupForms();
    setupCompetitionDetails();
}

// 设置导航功能
function setupNavigation() {
    const navToggle = document.querySelector('.nav-toggle');
    const navMenu = document.querySelector('.nav-menu');

    if (navToggle && navMenu) {
        const setMenuOpen = (open) => {
            navMenu.classList.toggle('active', open);
            navMenu.classList.toggle('nav-open', open);
            navToggle.classList.toggle('active', open);
            navToggle.setAttribute('aria-expanded', String(open));
        };

        setMenuOpen(false);
        navToggle.addEventListener('click', () => {
            setMenuOpen(!navMenu.classList.contains('nav-open'));
        });

        document.addEventListener('click', (event) => {
            if (!navMenu.contains(event.target) && !navToggle.contains(event.target)) {
                setMenuOpen(false);
            }
        });
    }

    // 平滑滚动
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
                // 关闭移动端菜单
                if (navMenu) {
                    navMenu.classList.remove('active');
                }
            }
        });
    });

    // 导航栏滚动效果
    window.addEventListener('scroll', () => {
        const navbar = document.querySelector('.navbar');
        if (window.scrollY > 100) {
            navbar.style.background = 'rgba(10, 10, 15, 0.98)';
        } else {
            navbar.style.background = 'rgba(10, 10, 15, 0.95)';
        }
    });
}

function setupLazyLoading() {
    const images = document.querySelectorAll('img.lazy-load[data-src]');
    if (!images.length) return;

    const loadImage = (image) => {
        const source = image.getAttribute('data-src');
        if (!source) return;
        image.src = source;
        image.removeAttribute('data-src');
        image.classList.remove('lazy-load');
    };

    if (!('IntersectionObserver' in window)) {
        images.forEach(loadImage);
        return;
    }

    const observer = new IntersectionObserver((entries, instance) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            loadImage(entry.target);
            instance.unobserve(entry.target);
        });
    }, { rootMargin: '120px 0px' });

    images.forEach((image) => observer.observe(image));
}

// 设置打字效果
function setupTypingEffect() {
    const typingElement = document.querySelector('.typing-text');
    if (!typingElement) return;

    function typeText() {
        if (isTyping) return;
        isTyping = true;

        const currentText = typingTexts[typingIndex];
        let charIndex = 0;

        // 清空当前文本
        typingElement.textContent = '';

        function addChar() {
            if (charIndex < currentText.length) {
                typingElement.textContent += currentText[charIndex];
                charIndex++;
                setTimeout(addChar, 150);
            } else {
                setTimeout(() => {
                    deleteText();
                }, 2000);
            }
        }

        function deleteText() {
            if (typingElement.textContent.length > 0) {
                typingElement.textContent = typingElement.textContent.slice(0, -1);
                setTimeout(deleteText, 100);
            } else {
                typingIndex = (typingIndex + 1) % typingTexts.length;
                isTyping = false;
                setTimeout(typeText, 500);
            }
        }

        addChar();
    }

    typeText();
}

// 设置滚动效果
function setupScrollEffects() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    // 观察需要动画的元素
    document.querySelectorAll('.competition-card, .student-card, .contact-form').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });
}

// 设置加载更多功能
function setupLoadMore() {
    // 比赛加载更多
    const loadMoreCompetitions = document.getElementById('loadMoreCompetitions');
    const moreCompetitions = document.getElementById('moreCompetitions');

    if (loadMoreCompetitions && moreCompetitions) {
        loadMoreCompetitions.addEventListener('click', () => {
            const isHidden = getComputedStyle(moreCompetitions).display === 'none';
            if (isHidden) {
                moreCompetitions.style.display = 'block';
                loadMoreCompetitions.innerHTML = '<i class="fas fa-chevron-up"></i> 收起更多赛事';
                loadMoreCompetitions.classList.add('rotated');
            } else {
                moreCompetitions.style.display = 'none';
                loadMoreCompetitions.innerHTML = '<i class="fas fa-chevron-down"></i> 加载更多赛事';
                loadMoreCompetitions.classList.remove('rotated');
            }
        });
    }

    // 科技特长生认证详情
    const loadMoreCertification = document.getElementById('loadMoreCertification');
    const certificationDetails = document.getElementById('certificationDetails');

    if (loadMoreCertification && certificationDetails) {
        loadMoreCertification.addEventListener('click', () => {
            const isHidden = getComputedStyle(certificationDetails).display === 'none';
            if (isHidden) {
                certificationDetails.style.display = 'block';
                loadMoreCertification.innerHTML = '<i class="fas fa-chevron-up"></i> 收起详细信息';
                loadMoreCertification.classList.add('rotated');
            } else {
                certificationDetails.style.display = 'none';
                loadMoreCertification.innerHTML = '<i class="fas fa-chevron-down"></i> 了解详细认证流程';
                loadMoreCertification.classList.remove('rotated');
            }
        });
    }

    // 学生案例加载更多
    const loadMoreStudents = document.getElementById('loadMoreStudents');
    const moreStudents = document.getElementById('moreStudents');

    if (loadMoreStudents && moreStudents) {
        loadMoreStudents.addEventListener('click', () => {
            const isHidden = getComputedStyle(moreStudents).display === 'none';
            if (isHidden) {
                moreStudents.style.display = 'block';
                loadMoreStudents.innerHTML = '<i class="fas fa-chevron-up"></i> 收起学生案例';
                loadMoreStudents.classList.add('rotated');
            } else {
                moreStudents.style.display = 'none';
                loadMoreStudents.innerHTML = '<i class="fas fa-chevron-down"></i> 查看更多学生案例';
                loadMoreStudents.classList.remove('rotated');
            }
        });
    }
}

// 设置聊天窗口
function setupChatWidget() {
    const chatButton = document.getElementById('chatButton');
    const chatWindow = document.getElementById('chatWindow');
    const chatClose = document.getElementById('chatClose');

    if (chatButton && chatWindow && chatClose) {
        chatButton.addEventListener('click', () => {
            chatWindow.classList.add('show');
        });

        chatClose.addEventListener('click', () => {
            chatWindow.classList.remove('show');
        });

        // 点击窗口外关闭
        document.addEventListener('click', (e) => {
            if (!chatWindow.contains(e.target) && !chatButton.contains(e.target)) {
                chatWindow.classList.remove('show');
            }
        });
    }

    // 快速问题按钮
    document.querySelectorAll('.quick-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const question = e.target.getAttribute('data-question');
            addChatMessage(question, 'user');

            // 模拟回复
            setTimeout(() => {
                let reply = '';
                switch(question) {
                    case '如何参加编程竞赛？':
                        reply = '您可以通过学校推荐或个人报名参加NOIP等编程竞赛。建议先从基础算法学起，可以联系我们获取详细的培训方案。';
                        break;
                    case '机器人比赛有哪些？':
                        reply = '主要有世界机器人大赛(WRC)、VEX机器人竞赛、FRC机器人竞赛等。宜昌地区每年都有相关培训和选拔赛。';
                        break;
                    case '如何申请特长生？':
                        reply = '需要先在相关竞赛中获奖，然后准备申报材料。宜昌市每年3月和9月有申报机会，欢迎留下联系方式获取详细指导。';
                        break;
                    default:
                        reply = '感谢您的咨询！请留下您的联系方式，我们的专业老师会尽快与您联系。';
                }
                addChatMessage(reply, 'bot');
            }, 1000);
        });
    });
}

// 添加聊天消息
function addChatMessage(message, sender) {
    const chatBody = document.querySelector('.chat-body');
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${sender}-message`;

    if (sender === 'user') {
        messageDiv.innerHTML = `<p style="background: rgba(0, 255, 255, 0.1); padding: 10px; border-radius: 15px; margin: 10px 0; text-align: right;">${message}</p>`;
    } else {
        messageDiv.innerHTML = `<p style="background: rgba(0, 255, 255, 0.1); padding: 12px; border-radius: 15px; color: #ffffff; margin: 10px 0;">${message}</p>`;
    }

    chatBody.appendChild(messageDiv);
    chatBody.scrollTop = chatBody.scrollHeight;
}

// 设置表单功能
function setupForms() {
    // 主联系表单
    const contactForm = document.getElementById('contactForm');
    if (contactForm) {
        contactForm.addEventListener('submit', handleContactSubmit);
    }

    // 快速联系表单
    const quickContactForm = document.getElementById('quickContactForm');
    if (quickContactForm) {
        quickContactForm.addEventListener('submit', handleQuickContactSubmit);
    }
}

// 获取或生成匿名用户ID
function getOrGenerateUserId() {
    let userId = localStorage.getItem('robotdoctor_user_id');
    if (!userId) {
        userId = 'user_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem('robotdoctor_user_id', userId);
    }
    return userId;
}

// 记录页面访问
async function recordPageVisit() {
    try {
        const userId = getOrGenerateUserId();
        const pageData = {
            userId: userId,
            page: window.location.pathname || '/',
            actionType: 'page_view',
            metadata: {
                title: document.title,
                timestamp: new Date().toISOString(),
                referrer: document.referrer,
                viewport: {
                    width: window.innerWidth,
                    height: window.innerHeight
                }
            }
        };

        await fetch('/api/visit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(pageData)
        });
    } catch (error) {
        console.warn('记录页面访问失败:', error);
    }
}

// 记录用户行为
async function recordUserAction(actionType, data = {}) {
    try {
        const userId = getOrGenerateUserId();
        const actionData = {
            userId: userId,
            page: window.location.pathname || '/',
            actionType: actionType,
            metadata: {
                ...data,
                timestamp: new Date().toISOString()
            }
        };

        await fetch('/api/visit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(actionData)
        });
    } catch (error) {
        console.warn('记录用户行为失败:', error);
    }
}

// 处理主联系表单提交
async function handleContactSubmit(e) {
    e.preventDefault();

    const formData = new FormData(e.target);
    const data = {
        name: formData.get('name'),
        phone: formData.get('phone'),
        message: formData.get('message'),
        userId: getOrGenerateUserId()
    };

    // 验证手机号
    if (!validatePhone(data.phone)) {
        showMessage('请输入正确的手机号码', 'error');
        return;
    }

    const submitBtn = e.target.querySelector('.submit-btn');
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<div class="loading"></div>正在提交...';
    submitBtn.disabled = true;

    try {
        const response = await fetch('/api/contact', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            showMessage('提交成功！我们会尽快与您联系', 'success');
            e.target.reset();
            // 记录成功提交行为
            await recordUserAction('contact_submit_success', { contactType: 'full' });
        } else {
            throw new Error('提交失败');
        }
    } catch (error) {
        console.error('Error:', error);
        showMessage('提交失败，请稍后重试或直接拨打电话联系我们', 'error');
        // 记录提交失败行为
        await recordUserAction('contact_submit_error', { contactType: 'full', error: error.message });
    } finally {
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    }
}

// 处理快速联系表单提交
async function handleQuickContactSubmit(e) {
    e.preventDefault();

    const phone = document.getElementById('quickPhone').value;

    if (!validatePhone(phone)) {
        showMessage('请输入正确的手机号码', 'error');
        return;
    }

    const data = {
        phone: phone,
        userId: getOrGenerateUserId()
    };

    const submitBtn = e.target.querySelector('button');
    const originalHTML = submitBtn.innerHTML;
    submitBtn.innerHTML = '<div class="loading"></div>';
    submitBtn.disabled = true;

    try {
        const response = await fetch('/api/quick-contact', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            showMessage('提交成功！我们会尽快与您联系', 'success');
            document.getElementById('quickPhone').value = '';
            addChatMessage('感谢您留下联系方式！我们的专业老师会在24小时内与您联系，为您提供个性化的科技竞赛指导方案。', 'bot');
            // 记录成功提交行为
            await recordUserAction('quick_contact_submit_success', { source: 'chat_widget' });
        } else {
            throw new Error('提交失败');
        }
    } catch (error) {
        console.error('Error:', error);
        showMessage('提交失败，请稍后重试', 'error');
        // 记录提交失败行为
        await recordUserAction('quick_contact_submit_error', { source: 'chat_widget', error: error.message });
    } finally {
        submitBtn.innerHTML = originalHTML;
        submitBtn.disabled = false;
    }
}

// 验证手机号
function validatePhone(phone) {
    const phoneRegex = /^1[3-9]\d{9}$/;
    return phoneRegex.test(phone);
}

// 显示消息
function showMessage(message, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `${type}-message`;
    messageDiv.textContent = message;

    // 找到合适的容器插入消息
    const container = document.querySelector('.contact-form') || document.querySelector('.chat-footer');
    if (container) {
        container.appendChild(messageDiv);

        setTimeout(() => {
            messageDiv.remove();
        }, 5000);
    }
}

// 设置比赛详情功能
function setupCompetitionDetails() {
    // The canonical page already provides the complete modal implementation.
    // Never replace it with the older simplified fallback.
    if (typeof window.showCompetitionDetail === 'function') {
        return;
    }

    // 为了演示，这里创建一个简单的模态框功能
    window.showCompetitionDetail = function(competitionId) {
        const competition = competitionDetails[competitionId];
        if (!competition) return;

        // 创建模态框
        const modal = document.createElement('div');
        modal.className = 'competition-modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>${competition.title}</h3>
                    <button class="modal-close" onclick="closeModal()">&times;</button>
                </div>
                <div class="modal-body">
                    <p>${competition.description}</p>

                    <h4>🎯 参赛流程</h4>
                    <ul>
                        ${competition.process.map(step => `<li>${step}</li>`).join('')}
                    </ul>

                    <h4>🏆 竞赛优势</h4>
                    <ul>
                        ${competition.benefits.map(benefit => `<li>${benefit}</li>`).join('')}
                    </ul>

                    <div class="modal-actions">
                        <a href="${competition.website}" target="_blank" class="btn btn-primary">
                            <i class="fas fa-external-link-alt"></i>
                            访问官网
                        </a>
                        <button class="btn btn-secondary" onclick="contactForCompetition('${competitionId}')">
                            <i class="fas fa-phone"></i>
                            咨询报名
                        </button>
                    </div>

                    <div class="contact-info">
                        <p><strong>联系方式：</strong>${competition.contact}</p>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        modal.style.display = 'flex';

        // 点击外部关闭
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal();
            }
        });
    };

    // 关闭模态框
    window.closeModal = function() {
        const modal = document.querySelector('.competition-modal');
        if (modal) {
            modal.remove();
        }
    };

    // 竞赛咨询
    window.contactForCompetition = function(competitionId) {
        const competition = competitionDetails[competitionId];
        if (competition) {
            // 关闭模态框
            closeModal();

            // 滚动到联系表单
            const contactSection = document.getElementById('contact');
            if (contactSection) {
                contactSection.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });

                // 在表单中预填比赛信息
                setTimeout(() => {
                    const messageField = document.getElementById('message');
                    if (messageField) {
                        messageField.value = `我想了解${competition.title}的详细信息和报名流程，请与我联系。`;
                        messageField.focus();
                    }
                }, 800);
            }
        }
    };
}

// 添加模态框样式（动态添加到head中）
function addModalStyles() {
    if (document.querySelector('#modal-styles')) return;

    const style = document.createElement('style');
    style.id = 'modal-styles';
    style.textContent = `
        .competition-modal {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 2000;
            opacity: 0;
            animation: fadeIn 0.3s ease forwards;
        }

        .modal-content {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            border-radius: 20px;
            padding: 0;
            max-width: 600px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
            border: 1px solid rgba(0, 255, 255, 0.2);
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            transform: translateY(30px);
            animation: slideUp 0.3s ease forwards;
        }

        .modal-header {
            padding: 25px;
            border-bottom: 1px solid rgba(0, 255, 255, 0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .modal-header h3 {
            color: #ffffff;
            margin: 0;
            font-size: 1.5rem;
        }

        .modal-close {
            background: none;
            border: none;
            color: #888;
            font-size: 2rem;
            cursor: pointer;
            padding: 0;
            line-height: 1;
            transition: color 0.3s ease;
        }

        .modal-close:hover {
            color: #ff6b6b;
        }

        .modal-body {
            padding: 25px;
        }

        .modal-body p {
            color: #b0b0b0;
            line-height: 1.6;
            margin-bottom: 20px;
        }

        .modal-body h4 {
            color: #ffffff;
            margin: 25px 0 15px;
            font-size: 1.2rem;
        }

        .modal-body ul {
            list-style: none;
            margin-bottom: 20px;
        }

        .modal-body li {
            color: #d0d0d0;
            margin-bottom: 10px;
            padding-left: 20px;
            position: relative;
            line-height: 1.5;
        }

        .modal-body li::before {
            content: '▶';
            position: absolute;
            left: 0;
            color: #00ffff;
        }

        .modal-actions {
            display: flex;
            gap: 15px;
            margin: 25px 0;
        }

        .contact-info {
            background: rgba(0, 255, 255, 0.05);
            border-radius: 10px;
            padding: 15px;
            border-left: 4px solid #00ffff;
        }

        .contact-info p {
            margin: 0;
            color: #ffffff;
        }

        @keyframes fadeIn {
            to { opacity: 1; }
        }

        @keyframes slideUp {
            to { transform: translateY(0); }
        }

        @media (max-width: 768px) {
            .modal-content {
                width: 95%;
                margin: 20px;
            }

            .modal-actions {
                flex-direction: column;
            }
        }
    `;

    document.head.appendChild(style);
}

// 页面加载完成后添加模态框样式
document.addEventListener('DOMContentLoaded', addModalStyles);
