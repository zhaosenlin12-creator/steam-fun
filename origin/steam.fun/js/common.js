// import store from "@/vuex";

window.urlParams = function (paramName) {
  var reg = new RegExp('[?&]' + paramName + '=([^&]*)[&]?', 'i')
  var paramVal = window.location.search.match(reg)
  return paramVal == null ? '' : decodeURIComponent(paramVal[1])
}

//字符串进行解密 
window.uncompileStr = function (code) {
  code = unescape(code);
  var c = String.fromCharCode(code.charCodeAt(0) - code.length);
  for (var i = 1; i < code.length; i++) {
    c += String.fromCharCode(code.charCodeAt(i) - c.charCodeAt(i - 1));
  }
  return c;
}

window.uuid = function () {
  var s = []
  var hexDigits = '0123456789abcdef'
  for (var i = 0; i < 36; i++) {
    s[i] = hexDigits.substr(Math.floor(Math.random() * 0x10), 1)
  }
  s[14] = '4' // bits 12-15 of the time_hi_and_version field to 0010
  s[19] = hexDigits.substr((s[19] & 0x3) | 0x8, 1) // bits 6-7 of the clock_seq_hi_and_reserved to 01
  s[8] = s[13] = s[18] = s[23] = '-'
  var uuid = s.join('')
  return uuid
}


window.getUserInfo = function () {
  userInfo = localStorage.getItem('pro__Login_Userinfo')
  if (userInfo) {
    userInfo = JSON.parse(userInfo).value
    //console.log(userInfo)
    return userInfo
  }
}

window.getUserToken = function () {
  var token = JSON.parse(localStorage.getItem("vuex"))
  return token == null ? null : token.user.token
}

window.UserStuInfo = function () {
  var vuex = JSON.parse(localStorage.getItem("vuex"))
  return vuex == null ? null : vuex.user.userInfo
}

window.getWorkInfo = function (workId, cb) {
  $.ajax({
    url: '/api/teaching/teachingWork/studentWorkInfo',
    data: {
      workId: workId
    },
    success: function (res) {
      if (res.code == 0) {
        cb(res.result)
      }
    },
    error: function (e) { }
  })
}

//获得讲次信息
window.getPlanInfo = function (access_token, plan_id, operate, cb) {
  $.ajax({
    url: '/api/get/stu/tch/plan/info/and/tch/work/info',
    type: 'GET',
    dataType: 'json',
    contentType: 'application/json',
    async: false,
    beforeSend: function (request) {
      request.setRequestHeader('Authorization', access_token);
    },
    data: {
      stuTchPlanId: plan_id,
      work_type: operate
    },
    success: function (res) {
      cb(res.content)
    },
    error: function () { },
    complete: function () { }
  })
}


//根据ID获得自由创作作品详情页
window.h5GetWorkContent = function (work_id, subject_code, cb) {
  $.ajax({
    url: '/api/h5/get/work/content',
    type: 'GET',
    dataType: 'json',
    contentType: 'application/json',
    async: false,
    data: {
      work_id: work_id,
      subject_code: subject_code
    },
    success: function (res) {
      cb(res.content)
    },
    error: function () { },
    complete: function () { }
  })
}


//根据ID获得自由创作作品详情页 - 新
window.h5GetWorkContentForNew = function (eduId, work_id, subject_code, cb) {
  $.ajax({
    url: '/api/h5/getWorkContentForNew',
    type: 'GET',
    dataType: 'json',
    contentType: 'application/json',
    async: false,
    data: {
      eduId: eduId,
      work_id: work_id,
      subject_code: subject_code
    },
    success: function (res) {
      cb(res.content)
    },
    error: function () { },
    complete: function () { }
  })
}


//根据ID获得课堂作品详情
window.h5GetTchWorkContent = function (work_id, subject_code, schoolIdTest, stuTchPlanIdTest, cb) {
  $.ajax({
    url: '/api/h5/get/tch/work/content',
    type: 'GET',
    dataType: 'json',
    contentType: 'application/json',
    async: false,
    data: {
      work_id,
      subject_code,
      schoolIdTest,
      stuTchPlanIdTest
    },
    success: function (res) {
      //console.log('课堂作品')
      //console.log(res)
      cb(res.content)
    },
    error: function () { },
    complete: function () { }
  })
}

//查询作者的其他作品
window.h5GetOneUserWorkList = function (subject_code, user_code, page_no, page_size, cb) {

  $.ajax({
    url: '/api/h5/get/one/user/work/list',
    type: 'GET',
    dataType: 'json',
    contentType: 'application/json',
    async: false,

    data: {
      subject_code: subject_code,
      user_code: user_code,
      title: "",
      page_no: page_no,
      page_size: page_size
    },
    success: function (res) {
      cb(res.content)
    },
    error: function () { },
    complete: function () { }
  })
}


//上传SC课堂作品
//上传文件
window.UploadWorks = function (access_token, uploadParam, cb) {
  var id = null;
  $.ajax({
    url: '/api/save/sc/tch/work',
    type: 'POST',
    dataType: 'json',
    contentType: 'application/x-www-form-urlencoded',
    async: false,
    beforeSend: function (request) {
      request.setRequestHeader('Authorization', access_token)
    },
    data: {
      stu_user_id: uploadParam.stu_user_id,
      stu_tch_plan_id: uploadParam.stu_tch_plan_id,
      work_url: uploadParam.work_url,
      covers: uploadParam.covers,
      title: uploadParam.title,
      is_local: uploadParam.is_local,
      abstract: uploadParam.abstract,
      explain: uploadParam.explain,
      work_type: uploadParam.work_type
    },
    success: function (res) {
      //console.log("保存作品");
      //console.log(res);
      cb(res);

    },
    error: function () { },
    complete: function () { }
  })
}


//修改课堂模板
window.updateTchPlanTemplate = function (access_token, uploadParam, cb) {
  var id = null;
  $.ajax({
    url: '/api/tch/update/tch/plan/template',
    type: 'POST',
    dataType: 'json',
    contentType: 'application/x-www-form-urlencoded',
    async: false,
    beforeSend: function (request) {
      request.setRequestHeader('Authorization', access_token)
    },
    data: {
      tchPlanId: uploadParam.tchPlanId,
      work_url: uploadParam.work_url,
      covers_url: uploadParam.covers_url,
      title: uploadParam.title,
      template_type: uploadParam.template_type,
    },
    success: function (res) {
      //console.log("修改上课模板");
      //console.log(res);
      cb(res.content);

    },
    error: function () { },
    complete: function () { }
  })
}


//老师保存课堂作品
window.saveTchLessonWork = function (access_token, uploadParam, cb) {

  if (!uploadParam.work_id) {
    $.ajax({
      url: '/api/save/tch/lesson/work',
      type: 'POST',
      dataType: 'json',
      contentType: 'application/x-www-form-urlencoded',
      async: false,
      beforeSend: function (request) {
        request.setRequestHeader('Authorization', access_token)
      },
      data: {
        tchPlanId: uploadParam.tchPlanId, //教学计划id
        work_url: uploadParam.work_url,
        covers: uploadParam.covers_url,
        title: uploadParam.title,
        lessonId: uploadParam.lessonId, //课程ID
        type: uploadParam.type
      },
      success: function (res) {
        cb(res);
      },
      error: function () { },
      complete: function () { }
    })

  }
  else {

    $.ajax({
      url: '/api/save/tch/lesson/work',
      type: 'POST',
      dataType: 'json',
      contentType: 'application/x-www-form-urlencoded',
      async: false,
      beforeSend: function (request) {
        request.setRequestHeader('Authorization', access_token)
      },
      data: {
        id: uploadParam.work_id,
        tchPlanId: uploadParam.tchPlanId, //教学计划id
        work_url: uploadParam.work_url,
        covers: uploadParam.covers_url,
        title: uploadParam.title,
        lessonId: uploadParam.lessonId, //课程ID
        type: uploadParam.type
      },
      success: function (res) {
        cb(res);
      },
      error: function () { },
      complete: function () { }
    })

  }
}

//老师删除课堂作品

window.deleteTchLessonWork = function (access_token, uploadParam, cb) {

  $.ajax({
    url: '/api/delete/tch/lesson/work',
    type: 'POST',
    dataType: 'json',
    contentType: 'application/x-www-form-urlencoded',
    async: false,
    beforeSend: function (request) {
      request.setRequestHeader('Authorization', access_token)
    },
    data: {
      id: uploadParam.id,
    },
    success: function (res) {
      //console.log("老师删除课堂作品");
      //console.log(res);
      cb(res.content);
    },
    error: function () { },
    complete: function () { }
  })
}




//提交JR课程作品
window.UploadJrWorks = function (access_token, uploadParam, cb) {
  var id = null;
  $.ajax({
    url: '/api/save/jr/tch/work',
    type: 'POST',
    dataType: 'json',
    contentType: 'application/x-www-form-urlencoded',
    async: false,
    beforeSend: function (request) {
      request.setRequestHeader('Authorization', access_token)
    },
    data: {
      stu_user_id: uploadParam.stu_user_id,
      stu_tch_plan_id: uploadParam.stu_tch_plan_id,
      work_url: uploadParam.work_url,
      covers: uploadParam.covers,
      title: uploadParam.title,
      is_local: uploadParam.is_local,
      work_type: uploadParam.work_type
    },
    success: function (res) {
      //console.log("保存作品");
      //console.log(res);
      cb(res.content);

    },
    error: function () { },
    complete: function () { }
  })
}


//上传文件
window.PublishWorks = function (access_token, uploadParam, cb) {

  //console.log("提交的参数");
  //console.log(uploadParam);

  if (!uploadParam.work_id) {
    $.ajax({
      url: '/api/save/sc/work',
      type: 'POST',
      dataType: 'json',
      contentType: 'application/x-www-form-urlencoded',
      async: false,
      beforeSend: function (request) {
        request.setRequestHeader('Authorization', access_token)
      },
      data: {
        work_type: uploadParam.work_type,
        work_url: uploadParam.work_url,
        covers: uploadParam.covers,
        title: uploadParam.title,
        abstract: uploadParam.abstract,
        isOnly: uploadParam.isOnly,
        work_tag: JSON.stringify(uploadParam.work_tag),
        explain: uploadParam.explain
      },
      success: function (res) {
        //console.log("res返回数据");
        //console.log(res);
        cb(res.content);

      },
      error: function () { },
      complete: function () { }
    })
  } else {
    $.ajax({
      url: '/api/save/sc/work',
      type: 'POST',
      dataType: 'json',
      contentType: 'application/x-www-form-urlencoded',
      async: false,
      beforeSend: function (request) {
        request.setRequestHeader('Authorization', access_token)
      },
      data: {
        work_id: uploadParam.work_id,
        work_type: uploadParam.work_type,
        work_url: uploadParam.work_url,
        covers: uploadParam.covers,
        title: uploadParam.title,
        abstract: uploadParam.abstract,
        isOnly: uploadParam.isOnly,
        work_tag: JSON.stringify(uploadParam.work_tag),
        explain: uploadParam.explain
      },
      success: function (res) {
        //console.log("作品更新");
        //console.log(res);
        cb(res.content);

      },
      error: function () { },
      complete: function () { }
    })
  }


}



//学生考试提交综合题项目
window.checkSingleQuestion = function (access_token, uploadParam, cb) {

  //console.log("提交的参数");
  //console.log(uploadParam);

  if (!uploadParam.stuExamQuestionId) {
    $.ajax({
      url: '/api/stuexam/check/single/question',
      type: 'POST',
      dataType: 'json',
      contentType: 'application/x-www-form-urlencoded',
      async: false,
      beforeSend: function (request) {
        request.setRequestHeader('Authorization', access_token)
      },
      data: {
        examId: uploadParam.exam_id,
        questionId: uploadParam.question_id,
        answer: uploadParam.answer,
      },
      success: function (res) {
        //console.log("res返回数据");
        //console.log(res);
        cb(res.content);

      },
      error: function () { },
      complete: function () { }
    })
  } else {
    $.ajax({
      url: '/api/stuexam/check/single/question',
      type: 'POST',
      dataType: 'json',
      contentType: 'application/x-www-form-urlencoded',
      async: false,
      beforeSend: function (request) {
        request.setRequestHeader('Authorization', access_token)
      },
      data: {
        examId: uploadParam.exam_id,
        questionId: uploadParam.question_id,
        answer: uploadParam.answer,
        stuExamQuestionId: uploadParam.stuExamQuestionId,
      },
      success: function (res) {
        //console.log("作品更新");
        //console.log(res);
        cb(res.content);

      },
      error: function () { },
      complete: function () { }
    })
  }


}




//上传文件
window.PublishJrWorks = function (access_token, uploadParam, cb) {

  //console.log("提交的参数");
  //console.log(uploadParam);

  if (!uploadParam.work_id) {
    $.ajax({
      url: '/api/save/jr/work',
      type: 'POST',
      dataType: 'json',
      contentType: 'application/x-www-form-urlencoded',
      async: false,
      beforeSend: function (request) {
        request.setRequestHeader('Authorization', access_token)
      },
      data: {
        work_type: uploadParam.work_type,
        work_url: uploadParam.work_url,
        covers: uploadParam.covers,
        title: uploadParam.title,
        is_only: false
      },
      success: function (res) {
        //console.log("res返回数据");
        //console.log(res);
        cb(res.content);

      },
      error: function () { },
      complete: function () { }
    })
  } else {
    //console.log("JR作品更新操作")
    $.ajax({
      url: '/api/save/jr/work',
      type: 'POST',
      dataType: 'json',
      contentType: 'application/x-www-form-urlencoded',
      async: false,
      beforeSend: function (request) {
        request.setRequestHeader('Authorization', access_token)
      },
      data: {
        work_id: uploadParam.work_id,
        work_type: uploadParam.work_type,
        work_url: uploadParam.work_url,
        covers: uploadParam.covers,
        title: uploadParam.title,
        is_only: false
      },
      success: function (res) {
        //console.log("作品更新");
        //console.log(res);
        cb(res.content);

      },
      error: function () { },
      complete: function () { }
    })
  }
}


//点赞JRCODE作品
window.updateJrWorkZanList = function (access_token, work_id, operate_state, cb) {
  var id = null;
  $.ajax({
    url: '/api/update/jr/work/zan/list',
    type: 'POST',
    dataType: 'json',
    contentType: 'application/x-www-form-urlencoded',
    async: false,
    beforeSend: function (request) {
      request.setRequestHeader('Authorization', access_token)
    },
    data: {
      work_id: work_id,
      operate_state: operate_state
    },
    success: function (res) {
      //console.log("作品点赞");
      //console.log(res);
      cb(res.content);

    },
    error: function () { },
    complete: function () { }
  })
}

//收藏JRCODE作品
window.updateJrWorkKeepList = function (access_token, work_id, operate_state, cb) {
  var id = null;
  $.ajax({
    url: '/api/update/jr/work/keep/list',
    type: 'POST',
    dataType: 'json',
    contentType: 'application/x-www-form-urlencoded',
    async: false,
    beforeSend: function (request) {
      request.setRequestHeader('Authorization', access_token)
    },
    data: {
      work_id: work_id,
      operate_state: operate_state
    },
    success: function (res) {
      //console.log("作品收藏");
      //console.log(res);
      cb(res.content);

    },
    error: function () { },
    complete: function () { }
  })
}

//更新JRCODE作品浏览次数
window.updateJrWorkLooks = function (access_token, work_id, cb) {
  var id = null;
  $.ajax({
    url: '/api/update/jr/work/looks',
    type: 'POST',
    dataType: 'json',
    contentType: 'application/x-www-form-urlencoded',
    async: false,
    beforeSend: function (request) {
      request.setRequestHeader('Authorization', access_token)
    },
    data: {
      work_id: work_id
    },
    success: function (res) {
      //console.log("更新作品浏览次数");
      //console.log(res);
      cb(res.content);

    },
    error: function () { },
    complete: function () { }
  })
}



//查看JR作品详情
window.getJrWorkContent = function (access_token, work_id, cb) {
  $.ajax({
    url: '/api/get/jr/work/content',
    type: 'GET',
    dataType: 'json',
    contentType: 'application/json',
    async: false,
    beforeSend: function (request) {
      request.setRequestHeader('Authorization', access_token);
    },
    data: {
      work_id: work_id
    },
    success: function (res) {
      cb(res.content)
    },
    error: function () { },
    complete: function () { }
  })
}





//初始化OSS
window.InitOss = function (access_token, cb) {

  $.ajax({
    url: '/api/get/aliyun/sts',
    type: 'GET',
    dataType: 'json',
    contentType: 'application/json',
    async: false,
    beforeSend: function (request) {
      request.setRequestHeader('Authorization', access_token);
    },
    success: function (res) {
      cb(res);
    },
    error: function () {
      //console.log('error');
    },
    complete: function () { }
  })
}


function createCode(id, src) {
  $('#' + id).html('')
  var qrcode = new QRCode(document.getElementById(id), {
    width: 250,
    height: 250
  })
  qrcode.makeCode(src)
}

function dataURLtoBlob(dataurl) {
  var arr = dataurl.split(','),
    mime = arr[0].match(/:(.*?);/)[1],
    bstr = atob(arr[1]),
    n = bstr.length,
    u8arr = new Uint8Array(n);
  while (n--) {
    u8arr[n] = bstr.charCodeAt(n);
  }
  return new Blob([u8arr], {
    type: mime
  });
}

//获得微信分享
window.getJSSDKSign = function (url, cb) {
  $.ajax({
    url: '/api/wechat/get/JSSDK/sign',
    type: 'GET',
    dataType: 'json',
    contentType: 'application/json',
    async: false,
    data: {
      url: url
    },
    success: function (res) {
      cb(res.content)
    },
    error: function () { },
    complete: function () { }
  })
}


// 身份与 src/vuex/modules/user.js identity 一致：1 老师/员工，2 学生（public 脚本无法使用 webpack 的 store，从 localStorage 读持久化 vuex）
window.getzk = function () {
  try {
    var raw = localStorage.getItem('vuex')
    if (!raw) return '2'
    var vuex = JSON.parse(raw)
    var id = vuex && vuex.user && vuex.user.identity
    if (id === 1 || id === '1') return '1'
    return '2'
  } catch (e) {
    return '2'
  }
}
// /community/sensitiveWord/check
/**
 * HTML 中可调用的社区敏感词检测（身份 1 → 教师端 school；否则 → 学生端 student）
 * @param {{ title: string, abstractText: string, comment: string }} params
 * @param {function(*)} [onSuccess] 成功时回调，参数为接口返回的 content
 * @param {function(*)} [onError] 失败时回调
 * @returns {object|undefined} jQuery jqXHR，未登录或参数非法时返回 undefined
 */
window.checkCommunitySensitiveWord = function (params, onSuccess, onError) {
  if (!params || typeof params !== 'object') {
    if (typeof onError === 'function') onError({ message: 'params 需为对象，包含 field、checkScope、text' })
    return undefined
  }
  var token = typeof window.getUserToken === 'function' ? window.getUserToken() : null
  if (!token) {
    if (typeof onError === 'function') onError({ message: '未登录或无法读取 token' })
    return undefined
  }
  var role = typeof window.getzk === 'function' ? window.getzk() : '2'
  var path =
    role === '1'
      ? '/java-api/school/community/sensitiveWord/check'
      : '/java-api/student/community/sensitiveWord/check'
  var url = path + '?t=' + new Date().getTime()
  var payload = JSON.stringify({
    title: params.title,
    abstractText: params.abstractText,
  })
  return $.ajax({
    url: url,
    type: 'POST',
    dataType: 'json',
    contentType: 'application/json; charset=UTF-8',
    data: payload,
    beforeSend: function (xhr) {
      xhr.setRequestHeader('Authorization', token)
      xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest')
    },
    success: function (res) {
      if (res && res.success === true) {
        if (typeof onSuccess === 'function') onSuccess(res.content)
      } else if (typeof onError === 'function') {
        onError(res && res.error != null ? res.error : res)
      }
    },
    error: function (xhr, status, err) {
      if (typeof onError === 'function') {
        var msg = err || status
        try {
          var body = xhr.responseJSON || (xhr.responseText && JSON.parse(xhr.responseText))
          if (body && body.error) msg = body.error
        } catch (e) {}
        onError(msg)
      }
    }
  })
}