from __future__ import annotations

import base64
import gzip
import hashlib
import json
import mimetypes
import re
import sqlite3
import zlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, parse_qsl, quote, unquote, urlencode, urljoin, urlparse, urlunparse

import brotli
import requests
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse

from .config import BASE_URL, STUDENT_LOGIN_PATH, TEACHER_LOGIN_PATH
from .capabilities import default_route_for_role, permission_tree_for_role, resolve_profile_role, roles_for_frontend_route
from .course_offline import build_course_asset_not_local_response, lookup_course_archive_asset
from .homepage import COMPETITIONS_ASSET_INDEX, COMPETITIONS_ASSET_PREFIX, COURSES_ASSET_ROOT, competitions_asset_path, courses_asset_path, homepage_asset_path, render_marketing_homepage
from .rewrite import is_same_origin_host, rewrite_external_urls
from .storage import MirrorStore
from .workspaces import build_workspace_payload, workspace_asset_path


LOGIN_HTML_PATH = Path(__file__).resolve().parent / "site_assets" / "login" / "index.html"
TEXTUAL_RESPONSE_MARKERS = ("json", "javascript", "css", "html", "svg", "xml", "text")
HOP_BY_HOP_HEADERS = {"content-length", "transfer-encoding", "content-encoding", "connection", "host"}
ASSET_FALLBACK_FILENAMES = {"favicon.ico", "manifest.json", "robots.txt", "asset-manifest.json", "service-worker.js", "sw.js"}
HASHED_FRONTEND_ASSET_PATTERN = re.compile(
    r"^(?P<prefix>.+)\.(?P<hash>[0-9a-f]{6,32})(?P<suffix>\.(?:css|js))$",
    re.IGNORECASE,
)
KNOWN_FRONTEND_RUNTIME_PATCHES = {
    "e.data.error.message": "(((e||{}).data||{}).error||{}).message",
    "e.data.error.code": "(((e||{}).data||{}).error||{}).code",
    "e.style[r]=n": "e.style&&(e.style[r]=n)",
}
KNOWN_FRONTEND_BUNDLE_REPAIRS = {
    '}),e&&"/"!==e.path||e.name)){if(e.name===t.name)return!1;this.handleRouteReady()}': (
        '}),e&&"/"!==e.path||e.name){if(e.name===t.name)return!1;this.handleRouteReady()}'
    ),
}
ADMIN_PREVIEW_TO_LOCAL_PPT_PATTERN = re.compile(
    r'this\.\$router\.push\(\{name:"look-curriculum",params:\{curriculumMaterial:([A-Za-z_$][\w$]*)\}\}\)'
)
VERSION_RELOAD_PATTERN = re.compile(r'e&&"(v\d+)"!=e\.version&&window\.location\.reload\(\)')
SPA_LOGOUT_PATTERN = re.compile(
    r'this\.\$store\.dispatch\("LogOut"\)\.then\(\(\)=>\{'
    r'sessionStorage\.setItem\("schoolInfo",null\),'
    r'localStorage\.removeItem\("editor_opentype"\),'
    r'this\.\$message\.success\("退出成功"\),'
    r'this\.\$router\.push\(\{path:"/"\}\),location\.reload\(\)\}\)'
)
ADMIN_SPA_LOGOUT_PATTERN = re.compile(
    r'this\.\$store\.dispatch\("AdminLogOut"\)\.then\(\(\)=>\{'
    r'this\.\$message\.success\("[^"]*"\),'
    r'this\.\$router\.push\(\{path:"/background/login"\}\),'
    r'sessionStorage\.setItem\("schoolInfo",null\)\}\)'
)
COURSE_BROWSER_SUPPORT_REDIRECT = (
    'e("data/html5-unsupported.html");',
    "performRedirectIfNeeded=function(){return!1};",
)
COURSE_PLAYER_DISABLE_RESUME_PROMPT_PATCHES = (
    ('&&"prompt"==this.G.settings().Vc().wu()', '&&"never"==this.G.settings().Vc().wu()'),
    ('wu(){return this.Iw}', 'wu(){return "never"}'),
)
EMPTY_REJECTION_GUARD = (
    "<script>"
    "window.addEventListener('unhandledrejection',function(event){"
    "if(event.reason===undefined||event.reason===null||event.reason===''){event.preventDefault();}"
    "});"
    "</script>"
)
GLOBAL_FCN_GUARD = (
    "<script>"
    "window.fcn=typeof window.fcn==='function'?window.fcn:function(){};"
    "var fcn=window.fcn;"
    "</script>"
)
EDITOR_OPEN_TYPE_GUARD = (
    "<script>"
    "try{if(!localStorage.getItem('editor_opentype')){localStorage.setItem('editor_opentype','old');}}catch(e){}"
    "</script>"
)
CLASSROOM_PPT_LAYOUT_GUARD = (
    "<script>"
    "(function(){"
    "var path=location.pathname||'';"
    "if(/\\/code-classroom\\/(prepare-lessons\\/prepare|teach-lessons\\/lessons)\\/ppt(?:\\/)?$/.test(path)){"
    "document.documentElement.classList.add('local-classroom-ppt');"
    "}"
    "}());"
    "</script>"
    "<style>"
    "@media (max-width: 1100px){"
    "html.local-classroom-ppt body,"
    "html.local-classroom-ppt #app,"
    "html.local-classroom-ppt #app>.container,"
    "html.local-classroom-ppt .school-home-page,"
    "html.local-classroom-ppt .school-home-page>.frame{min-width:0!important;width:100%!important;max-width:100%!important;}"
    "html.local-classroom-ppt .school-home-page>.frame{display:block!important;}"
    "html.local-classroom-ppt .school-home-page>.frame>.menu{display:none!important;}"
    "html.local-classroom-ppt .school-home-page>.frame>section{display:block!important;width:100%!important;max-width:100%!important;}"
    "html.local-classroom-ppt .school-home-page>.frame>section>.el-header.prepare-header{width:100%!important;overflow-x:auto!important;white-space:nowrap!important;}"
    "html.local-classroom-ppt .school-home-page>.frame>section>.el-container{display:block!important;width:100%!important;}"
    "html.local-classroom-ppt .school-home-page>.frame>section>.el-container>.el-aside.leftpanel{display:none!important;}"
    "html.local-classroom-ppt .school-home-page>.frame>section>.el-container>.el-main.container{display:block!important;width:100%!important;max-width:100%!important;padding:8px!important;overflow:visible!important;}"
    "html.local-classroom-ppt .school-home-page .container>.el-row{display:block!important;}"
    "html.local-classroom-ppt .school-home-page .container>.el-row>.el-col.el-col-18,"
    "html.local-classroom-ppt .school-home-page .container>.el-row>.content_right.el-col.el-col-6{float:none!important;width:100%!important;max-width:100%!important;}"
    "html.local-classroom-ppt .school-home-page .content_right{margin-top:12px!important;}"
    "html.local-classroom-ppt .school-home-page .course-left,"
    "html.local-classroom-ppt .school-home-page .course-left-ppt,"
    "html.local-classroom-ppt .school-home-page .course-view{display:block!important;width:100%!important;max-width:100%!important;min-width:0!important;}"
    "html.local-classroom-ppt .school-home-page .course-view{min-height:60vh!important;}"
    "}"
    "</style>"
)
STUDENT_MYCLASS_LAYOUT_GUARD = (
    "<script>"
    "(function(){"
    "if(window.__localStudentMyClassLayout){return;}"
    "window.__localStudentMyClassLayout=true;"
    "if(/\\/code-classroom\\/myClass(?:\\/)?$/.test(location.pathname||'')){"
    "document.documentElement.classList.add('local-student-myclass');"
    "}"
    "}());"
    "</script>"
    "<style>"
    "@media(max-width:760px){"
    "html.local-student-myclass,html.local-student-myclass body,"
    "html.local-student-myclass #app,html.local-student-myclass #app>.container,"
    "html.local-student-myclass .school-home-page,html.local-student-myclass .school-home-page>.frame{"
    "min-width:0!important;width:100%!important;max-width:100%!important;overflow-x:hidden!important;}"
    "html.local-student-myclass #home_top>.el-row,"
    "html.local-student-myclass #header_other>.el-row{display:flex!important;align-items:center!important;padding:0 12px!important;}"
    "html.local-student-myclass #header_other>.el-row>.el-col-4{display:none!important;}"
    "html.local-student-myclass #header_other>.el-row>.el-col-14{float:none!important;flex:1 1 auto!important;width:auto!important;}"
    "html.local-student-myclass #header_other>.el-row>.el-col-6{float:none!important;flex:0 0 auto!important;width:auto!important;margin-left:auto!important;}"
    "html.local-student-myclass #header_other>.el-row>.el-col-6 .el-col-18{display:none!important;}"
    "html.local-student-myclass #header_other>.el-row>.el-col-6 .el-col-6{float:none!important;width:auto!important;}"
    "html.local-student-myclass #header_other .el-menu--horizontal>.el-menu-item{padding:0 10px!important;}"
    "html.local-student-myclass .school-home-page>.frame{display:block!important;padding-bottom:68px!important;}"
    "html.local-student-myclass .school-home-page>.frame>.menu{position:fixed!important;left:0!important;right:0!important;bottom:0!important;top:auto!important;z-index:120!important;display:block!important;width:100%!important;height:64px!important;min-height:0!important;background:#fff!important;box-shadow:0 -4px 18px rgba(32,45,64,.12)!important;}"
    "html.local-student-myclass .school-home-page>.frame>.menu>.el-row,"
    "html.local-student-myclass .school-home-page>.frame>.menu>.collapse-trigger{display:none!important;}"
    "html.local-student-myclass .school-home-page>.frame>.menu>.el-menu-demo{display:flex!important;width:100%!important;height:64px!important;margin:0!important;border:0!important;overflow-x:auto!important;overflow-y:hidden!important;}"
    "html.local-student-myclass .school-home-page>.frame>.menu>.el-menu-demo>.el-menu-item,"
    "html.local-student-myclass .school-home-page>.frame>.menu>.el-menu-demo>.el-submenu{display:flex!important;flex:1 0 76px!important;min-width:76px!important;height:64px!important;align-items:center!important;justify-content:center!important;padding:0 6px!important;line-height:1.2!important;}"
    "html.local-student-myclass .school-home-page>.frame>.menu>.el-menu-demo>.el-menu-item{flex-direction:column!important;gap:5px!important;}"
    "html.local-student-myclass .school-home-page>.frame>.menu>.el-menu-demo>.el-submenu>.el-submenu__title{display:flex!important;width:100%!important;height:64px!important;align-items:center!important;justify-content:center!important;flex-direction:column!important;gap:5px!important;padding:0 6px!important;line-height:1.2!important;}"
    "html.local-student-myclass .school-home-page>.frame>.menu>.el-menu-demo .icon{margin:0!important;font-size:18px!important;}"
    "html.local-student-myclass .school-home-page>.frame>.menu>.el-menu-demo span{font-size:11px!important;white-space:nowrap!important;}"
    "html.local-student-myclass .school-home-page>.frame>.menu>.el-menu-demo .el-submenu__icon-arrow{display:none!important;}"
    "html.local-student-myclass .school-home-page>.frame>section,"
    "html.local-student-myclass .school-home-page>.frame>section>.container{display:block!important;width:100%!important;max-width:100%!important;min-width:0!important;overflow:visible!important;}"
    "html.local-student-myclass .school-body-index-teacher{width:auto!important;max-width:none!important;min-width:0!important;margin:10px 8px!important;padding:14px!important;}"
    "html.local-student-myclass .school-body-index-teacher .el-tabs__nav-wrap{padding:0 20px!important;}"
    "html.local-student-myclass .school-body-index-teacher .filter-row{display:flex!important;flex-wrap:wrap!important;gap:8px!important;}"
    "html.local-student-myclass .school-body-index-teacher .el-form--inline .el-form-item{max-width:100%!important;margin-right:8px!important;}"
    "html.local-student-myclass .school-body-index-teacher .w-200{width:min(200px,calc(100vw - 82px))!important;}"
    "html.local-student-myclass .school-body-index-teacher .el-checkbox-group{display:flex!important;flex-wrap:wrap!important;gap:8px 12px!important;}"
    "html.local-student-myclass .school-body-index-teacher .el-checkbox{margin-right:0!important;}"
    "html.local-student-myclass .school-body-index-teacher .class-list-wrapper .el-col{width:100%!important;max-width:100%!important;}"
    "html.local-student-myclass .school-body-index-teacher .pagination-container{overflow-x:auto!important;padding-bottom:4px!important;}"
    "html.local-student-myclass .school-body-index-teacher .el-pagination{white-space:nowrap!important;}"
    "html.local-student-myclass .school-body-index-teacher .el-pagination__jump{display:none!important;}"
    "}"
    "</style>"
)
TEACHER_CLASSROOM_INDEX_LAYOUT_GUARD = (
    "<script>"
    "(function(){"
    "if(window.__localTeacherClassroomIndexLayout){return;}"
    "window.__localTeacherClassroomIndexLayout=true;"
    "if(/\\/code-classroom\\/classroom-index(?:\\/)?$/.test(location.pathname||'')){"
    "document.documentElement.classList.add('local-teacher-classroom-index');"
    "}"
    "}());"
    "</script>"
    "<style>"
    "@media(max-width:760px){"
    "html.local-teacher-classroom-index,html.local-teacher-classroom-index body,"
    "html.local-teacher-classroom-index #app,html.local-teacher-classroom-index #app>.container,"
    "html.local-teacher-classroom-index .school-home-page,html.local-teacher-classroom-index .school-home-page>.frame,"
    "html.local-teacher-classroom-index .school-home-page>.frame>section,"
    "html.local-teacher-classroom-index .school-home-page>.frame>section>.container{"
    "min-width:0!important;width:100%!important;max-width:100%!important;overflow-x:hidden!important;}"
    "html.local-teacher-classroom-index .school-home-page>.frame{"
    "display:block!important;padding-bottom:68px!important;}"
    "html.local-teacher-classroom-index .school-home-page>.frame>.menu{"
    "position:fixed!important;left:0!important;right:0!important;bottom:0!important;top:auto!important;"
    "z-index:120!important;display:block!important;width:100%!important;height:64px!important;min-height:0!important;"
    "background:#fff!important;box-shadow:0 -4px 18px rgba(32,45,64,.12)!important;}"
    "html.local-teacher-classroom-index .school-home-page>.frame>.menu>.el-row,"
    "html.local-teacher-classroom-index .school-home-page>.frame>.menu>.collapse-trigger{display:none!important;}"
    "html.local-teacher-classroom-index .school-home-page>.frame>.menu>.el-menu-demo{"
    "display:flex!important;width:100%!important;height:64px!important;margin:0!important;border:0!important;"
    "overflow-x:auto!important;overflow-y:hidden!important;}"
    "html.local-teacher-classroom-index .school-home-page>.frame>.menu>.el-menu-demo>.el-menu-item,"
    "html.local-teacher-classroom-index .school-home-page>.frame>.menu>.el-menu-demo>.el-submenu{"
    "display:flex!important;flex:1 0 82px!important;min-width:82px!important;height:64px!important;"
    "align-items:center!important;justify-content:center!important;padding:0 6px!important;line-height:1.2!important;}"
    "html.local-teacher-classroom-index .school-home-page>.frame>.menu>.el-menu-demo>.el-menu-item{"
    "flex-direction:column!important;gap:5px!important;}"
    "html.local-teacher-classroom-index .school-home-page>.frame>.menu>.el-menu-demo>.el-submenu>.el-submenu__title{"
    "display:flex!important;width:100%!important;height:64px!important;align-items:center!important;"
    "justify-content:center!important;flex-direction:column!important;gap:5px!important;"
    "padding:0 6px!important;line-height:1.2!important;}"
    "html.local-teacher-classroom-index .school-home-page>.frame>.menu>.el-menu-demo .icon{"
    "margin:0!important;font-size:18px!important;}"
    "html.local-teacher-classroom-index .school-home-page>.frame>.menu>.el-menu-demo span{"
    "font-size:11px!important;white-space:nowrap!important;}"
    "html.local-teacher-classroom-index .school-home-page>.frame>.menu>.el-menu-demo .el-submenu__icon-arrow{"
    "display:none!important;}"
    "html.local-teacher-classroom-index #home_top,"
    "html.local-teacher-classroom-index #header_other{"
    "height:60px!important;min-height:60px!important;overflow:hidden!important;}"
    "html.local-teacher-classroom-index #header_other>.el-row{"
    "display:flex!important;flex-wrap:nowrap!important;align-items:center!important;height:60px!important;"
    "padding:0 10px!important;box-sizing:border-box!important;overflow:hidden!important;}"
    "html.local-teacher-classroom-index #header_other>.el-row>.el-col-4{"
    "float:none!important;flex:0 0 52px!important;width:52px!important;min-width:52px!important;overflow:hidden!important;}"
    "html.local-teacher-classroom-index #header_other>.el-row>.el-col-14{"
    "float:none!important;flex:1 1 auto!important;width:auto!important;min-width:0!important;overflow:hidden!important;}"
    "html.local-teacher-classroom-index #header_other>.el-row>.el-col-14 .el-menu--horizontal{"
    "display:flex!important;width:100%!important;max-width:100%!important;overflow-x:auto!important;overflow-y:hidden!important;"
    "white-space:nowrap!important;}"
    "html.local-teacher-classroom-index #header_other>.el-row>.el-col-6{"
    "float:none!important;flex:0 0 auto!important;width:auto!important;min-width:0!important;max-width:56px!important;"
    "margin-left:auto!important;overflow:hidden!important;}"
    "html.local-teacher-classroom-index #header_other>.el-row>.el-col-6 .el-col-18{display:none!important;}"
    "html.local-teacher-classroom-index #header_other>.el-row>.el-col-6 .el-col-6{"
    "float:none!important;width:auto!important;min-width:0!important;}"
    "html.local-teacher-classroom-index .school-home-page>.frame>section,"
    "html.local-teacher-classroom-index .school-home-page>.frame>section>.container{"
    "display:block!important;min-width:0!important;width:100%!important;max-width:100%!important;overflow:visible!important;}"
    "html.local-teacher-classroom-index .school-body-teacher-index{"
    "width:auto!important;max-width:none!important;min-width:0!important;height:auto!important;"
    "min-height:calc(100vh - 188px)!important;margin:5px 0!important;padding:0!important;"
    "overflow-x:hidden!important;overflow-y:auto!important;}"
    "html.local-teacher-classroom-index .school-body-teacher-index .calendar-card,"
    "html.local-teacher-classroom-index .school-body-teacher-index .wrapper-up-content,"
    "html.local-teacher-classroom-index .school-body-teacher-index .wrapper-down-content{"
    "box-sizing:border-box!important;width:100%!important;max-width:100%!important;min-width:0!important;}"
    "html.local-teacher-classroom-index .school-body-teacher-index .el-row--flex{"
    "flex-wrap:wrap!important;}"
    "html.local-teacher-classroom-index .school-body-teacher-index .el-row--flex>.el-col{"
    "flex:0 0 100%!important;width:100%!important;max-width:100%!important;min-width:0!important;}"
    "html.local-teacher-classroom-index .school-body-teacher-index .calendar-card,"
    "html.local-teacher-classroom-index .school-body-teacher-index .wrapper-up-content,"
    "html.local-teacher-classroom-index .school-body-teacher-index .wrapper-down-content{"
    "width:calc(100% - 10px)!important;margin:5px!important;}"
    "html.local-teacher-classroom-index .school-body-teacher-index .calendar-nav{"
    "box-sizing:border-box!important;width:100%!important;min-width:0!important;}"
    "html.local-teacher-classroom-index .school-body-teacher-index .calendar-days{"
    "box-sizing:border-box!important;min-width:0!important;overflow:hidden!important;}"
    "html.local-teacher-classroom-index .school-body-teacher-index .classname .el-tooltip{"
    "display:block!important;max-width:100%!important;overflow:hidden!important;text-overflow:ellipsis!important;"
    "white-space:nowrap!important;}"
    "html.local-teacher-classroom-index .school-body-teacher-index .weekday-item,"
    "html.local-teacher-classroom-index .school-body-teacher-index .date-item-wrapper{"
    "box-sizing:border-box!important;min-width:0!important;}"
    "}"
    "</style>"
)
CLASSROOM_LOADING_FEEDBACK_GUARD = (
    "<script>"
    "(function(){"
    "if(window.__localClassroomLoadingUi){return;}"
    "window.__localClassroomLoadingUi=true;"
    "var classroomPath=/\\/code-classroom\\/(prepare-lessons\\/prepare|teach-lessons\\/lessons)\\/ppt(?:\\/)?$/;"
    "function isClassroomPpt(){return classroomPath.test(location.pathname||'');}"
    "if(!isClassroomPpt()){return;}"
    "var style=document.createElement('style');"
    "style.textContent='"
    ".local-course-loading-overlay{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;"
    "background:rgba(247,249,252,.76);backdrop-filter:blur(2px);z-index:9998;opacity:0;pointer-events:none;"
    "transition:opacity .18s ease;}"+
    ".local-course-loading-overlay.is-visible{opacity:1;pointer-events:auto;}"+
    ".local-course-loading-card{display:flex;align-items:center;gap:12px;background:rgba(17,24,39,.88);color:#fff;"
    "padding:14px 18px;border-radius:14px;box-shadow:0 10px 30px rgba(15,23,42,.18);font-size:14px;line-height:1.4;}"+
    ".local-course-loading-spinner{width:18px;height:18px;border-radius:999px;border:2px solid rgba(255,255,255,.28);"
    "border-top-color:#fff;animation:local-course-spin .85s linear infinite;}"+
    ".local-course-loading-progress{margin-top:4px;font-size:12px;color:rgba(255,255,255,.72);}"+
    ".local-course-loading-host{position:relative;}"+
    ".local-course-loading-host::after{content:\"\";position:absolute;inset:0;border-radius:12px;background:rgba(255,255,255,.38);"
    "backdrop-filter:blur(1px);opacity:0;pointer-events:none;transition:opacity .18s ease;}"+
    ".local-course-loading-host.is-loading::after{opacity:1;pointer-events:auto;}"+
    "@keyframes local-course-spin{to{transform:rotate(360deg);}}';"
    "document.head.appendChild(style);"
    "var overlay=document.createElement('div');"
    "overlay.className='local-course-loading-overlay';"
    "overlay.innerHTML='<div class=\"local-course-loading-card\"><div class=\"local-course-loading-spinner\"></div><div><div class=\"local-course-loading-text\">正在加载资源</div><div class=\"local-course-loading-progress\">请稍候，已收到操作请求</div></div></div>';"
    "function ensureOverlay(){if(!overlay.isConnected){var mountTarget=document.body||document.documentElement;if(mountTarget){mountTarget.appendChild(overlay);}}return overlay;}"
    "var visibleCount=0;"
    "var activeTimer=0;"
    "function setMessage(text,detail){ensureOverlay();"
    "var title=overlay.querySelector('.local-course-loading-text');"
    "var progress=overlay.querySelector('.local-course-loading-progress');"
    "if(title&&text){title.textContent=text;}"
    "if(progress&&detail){progress.textContent=detail;}"
    "}"
    "function showLoading(text,detail){"
    "clearTimeout(activeTimer);"
    "visibleCount+=1;"
    "setMessage(text||'正在加载资源',detail||'请稍候，已收到操作请求');"
    "ensureOverlay().classList.add('is-visible');"
    "document.documentElement.classList.add('local-course-loading');"
    "var host=document.querySelector('.course-view,.course-left-ppt,.course-left');"
    "if(host){host.classList.add('local-course-loading-host','is-loading');}"
    "}"
    "function hideLoading(force){"
    "if(force){visibleCount=0;}else if(visibleCount>0){visibleCount-=1;}"
    "if(visibleCount>0){return;}"
    "clearTimeout(activeTimer);"
    "overlay.classList.remove('is-visible');"
    "document.documentElement.classList.remove('local-course-loading');"
    "document.querySelectorAll('.local-course-loading-host.is-loading').forEach(function(node){node.classList.remove('is-loading');});"
    "}"
    "function pulseLoading(text,detail,timeout){"
    "showLoading(text,detail);"
    "clearTimeout(activeTimer);"
    "activeTimer=setTimeout(function(){hideLoading(true);},timeout||12000);"
    "}"
    "var lastInteractionPulseAt=0;"
    "function maybePulseFromInteraction(event){"
    "if(!matchesActionTarget(event.target)){return;}"
    "var text=((event.target.innerText||'')+(event.target.textContent||'')).replace(/\\s+/g,'');"
    "if(!/课堂成果|授课模板|作业模板|模板同步|学习资料|学生讲义|学生作品|作品社区|开始创作|点名上课|反馈/.test(text)){return;}"
    "var now=Date.now();"
    "if(now-lastInteractionPulseAt<800){return;}"
    "lastInteractionPulseAt=now;"
    "pulseLoading('正在打开内容','已收到操作请求，正在准备资源',15000);"
    "}"
    "function armIframe(iframe){"
    "if(!iframe||iframe.__localLoadingBound){return;}"
    "iframe.__localLoadingBound=true;"
    "try{if(iframe.contentDocument&&iframe.contentDocument.readyState==='complete'){setTimeout(function(){hideLoading(true);},4500);}}catch(e){}"
    "iframe.addEventListener('load',function(){hideLoading(true);});"
    "}"
    "function bindExistingIframes(){document.querySelectorAll('iframe').forEach(armIframe);}"
    "function matchesActionTarget(node){"
    "if(!node||!node.closest){return false;}"
    "return !!node.closest('.content_right,.course-tool,.course-tools,.el-drawer,.el-dialog,.el-button,button,[role=\"button\"],.el-tabs__item');"
    "}"
    "document.addEventListener('pointerdown',maybePulseFromInteraction,true);"
    "document.addEventListener('click',maybePulseFromInteraction,true);"
    "window.addEventListener('beforeunload',function(){showLoading('正在打开内容','即将跳转，请稍候');});"
    "window.addEventListener('message',function(){bindExistingIframes();});"
    "var observer=new MutationObserver(function(mutations){"
    "var shouldPulse=false;"
    "for(var i=0;i<mutations.length;i+=1){"
    "var mutation=mutations[i];"
    "for(var j=0;j<mutation.addedNodes.length;j+=1){"
    "var node=mutation.addedNodes[j];"
    "if(!node||node.nodeType!==1){continue;}"
    "if(node.matches&&node.matches('iframe')){armIframe(node);shouldPulse=true;}"
    "if(node.querySelectorAll){node.querySelectorAll('iframe').forEach(function(child){armIframe(child);shouldPulse=true;});}"
    "if(node.matches&&node.matches('.el-drawer,.el-dialog,.v-modal,.el-loading-mask')){shouldPulse=true;}"
    "}"
    "}"
    "if(shouldPulse){pulseLoading('正在加载资源','内容面板已打开，等待资源就绪',12000);setTimeout(function(){hideLoading(true);},4500);}"
    "});"
    "observer.observe(document.documentElement,{childList:true,subtree:true});"
    "bindExistingIframes();"
    "pulseLoading('正在加载资源','正在准备课件内容',10000);"
    "setTimeout(function(){hideLoading(true);},1800);"
    "}());"
    "</script>"
)
CORE_ROUTE_CLEANUP_GUARD = (
    "<script>"
    "(function(){"
    "if(window.__localCoreRouteCleanup){return;}"
    "window.__localCoreRouteCleanup=true;"
    "var allowedSubmenus=['教务中心','课程中心'];"
    "var allowedMenuItems=['学员管理','班级管理','教学计划','课程管理'];"
    "function hide(node){"
    "if(!node||node.nodeType!==1||node.__localCoreRouteCleanupHidden){return;}"
    "node.__localCoreRouteCleanupHidden=true;"
    "node.style.setProperty('display','none','important');"
    "node.setAttribute('aria-hidden','true');"
    "}"
    "function normalizedText(node){"
    "return ((node&&node.textContent)||'').replace(/\\s+/g,'').trim();"
    "}"
    "function matchesAny(text, labels){"
    "for(var i=0;i<labels.length;i+=1){"
    "if(text.indexOf(labels[i])!==-1){return true;}"
    "}"
    "return false;"
    "}"
    "function keepSubmenu(text){"
    "return matchesAny(text, allowedSubmenus);"
    "}"
    "function keepMenuItem(text){"
    "return matchesAny(text, allowedMenuItems);"
    "}"
    "function clean(root){"
    "if(!root||!root.querySelectorAll){return;}"
    "root.querySelectorAll('.el-submenu,.el-menu-item,[role=\"menuitem\"]').forEach(function(node){"
    "var text=normalizedText(node);"
    "var className=((node.className||'')+'').toLowerCase();"
    "if(className.indexOf('el-submenu')!==-1){"
    "if(!keepSubmenu(text)){hide(node);}"
    "return;"
    "}"
    "if(className.indexOf('el-menu-item')!==-1){"
    "if(!keepMenuItem(text)){hide(node);}"
    "return;"
    "}"
    "if(!keepMenuItem(text)){hide(node.closest('.el-menu-item,.el-submenu,[role=\"menuitem\"],li')||node);}"
    "});"
    "}"
    "function schedule(){clean(document.body||document.documentElement);}"
    "if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',schedule,{once:true});}else{schedule();}"
    "new MutationObserver(function(){schedule();}).observe(document.documentElement,{childList:true,subtree:true});"
    "}());"
    "</script>"
)
CORE_STUDENT_UI_CLEANUP_GUARD = (
    "<script>"
    "(function(){"
    "if(window.__localCoreStudentUiCleanup){return;}"
    "window.__localCoreStudentUiCleanup=true;"
    "var studentListPath=/\\/school-home-page\\/class-management1\\/students-management1(?:\\/)?$/;"
    "var addStudentPath=/\\/school-home-page\\/class-management1\\/addnewstudent1(?:\\/)?$/;"
    "var managementLabels=['鎵归噺鎿嶄綔骞冲彴鏉冮檺','缁戝畾寰俊'];"
    "var addStudentLabels=['骞冲彴鏉冮檺','浣滃搧绀惧尯','璧涜€冧腑蹇?,'鏌ョ湅棰樿В','瀛︾敓璁蹭箟'];"
    "function normalizedText(node){"
    "return ((node&&(node.innerText||node.textContent))||'').replace(/\\s+/g,'').trim();"
    "}"
    "function shouldHide(text,labels){"
    "if(!text||text.length>48){return false;}"
    "for(var i=0;i<labels.length;i+=1){"
    "var label=labels[i];"
    "if(text===label||text===label+':'||text.indexOf(label)!==-1){return true;}"
    "}"
    "return false;"
    "}"
    "function hide(node){"
    "if(!node||node.nodeType!==1||node.__localCoreStudentUiHidden){return;}"
    "node.__localCoreStudentUiHidden=true;"
    "node.style.setProperty('display','none','important');"
    "node.setAttribute('aria-hidden','true');"
    "}"
    "function hideClosest(node){"
    "var target=node.closest('.el-form-item,.el-dropdown-menu__item,.el-button,.el-col,.el-row,li,div')||node;"
    "hide(target);"
    "}"
    "function activeLabels(){"
    "var path=location.pathname||'';"
    "if(studentListPath.test(path)){return managementLabels;}"
    "if(addStudentPath.test(path)){return addStudentLabels;}"
    "return null;"
    "}"
    "function clean(){"
    "var labels=activeLabels();"
    "if(!labels){return;}"
    "var root=document.body||document.documentElement;"
    "if(!root||!root.querySelectorAll){return;}"
    "root.querySelectorAll('*').forEach(function(node){"
    "var text=normalizedText(node);"
    "if(shouldHide(text,labels)){hideClosest(node);}"
    "});"
    "}"
    "function schedule(){clean();}"
    "if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',schedule,{once:true});}else{schedule();}"
    "new MutationObserver(function(){schedule();}).observe(document.documentElement,{childList:true,subtree:true});"
    "}());"
    "</script>"
)
CORE_STUDENT_UI_CLEANUP_GUARD_V2 = (
    "<script>"
    "(function(){"
    "if(window.__localCoreStudentUiCleanupV2){return;}"
    "window.__localCoreStudentUiCleanupV2=true;"
    "var studentListPath=/\\/school-home-page\\/class-management1\\/students-management1(?:\\/)?$/;"
    "var addStudentPath=/\\/school-home-page\\/class-management1\\/addnewstudent1(?:\\/)?$/;"
    "var managementLabels=['\\u6279\\u91cf\\u64cd\\u4f5c\\u5e73\\u53f0\\u6743\\u9650','\\u7ed1\\u5b9a\\u5fae\\u4fe1','\\u91cd\\u7f6e\\u5bc6\\u7801','\\u9000\\u5b66','\\u5220\\u9664'];"
    "var addStudentLabels=['\\u5e73\\u53f0\\u6743\\u9650','\\u4f5c\\u54c1\\u793e\\u533a','\\u8d5b\\u8003\\u4e2d\\u5fc3','\\u67e5\\u770b\\u9898\\u89e3','\\u5b66\\u751f\\u8bb2\\u4e49'];"
    "function normalizedText(node){return ((node&&(node.innerText||node.textContent))||'').replace(/\\s+/g,'').trim();}"
    "function shouldHide(text,labels){"
    "if(!text||text.length>48){return false;}"
    "for(var i=0;i<labels.length;i+=1){"
    "var label=labels[i];"
    "if(text===label||text===label+':'||text.indexOf(label)!==-1){return true;}"
    "}"
    "return false;"
    "}"
    "function hide(node){"
    "if(!node||node.nodeType!==1||node.__localCoreStudentUiHiddenV2){return;}"
    "node.__localCoreStudentUiHiddenV2=true;"
    "node.style.setProperty('display','none','important');"
    "node.setAttribute('aria-hidden','true');"
    "}"
    "function hideClosest(node,selectors){hide(node.closest(selectors)||node);}"
    "function cleanManagement(root){"
    "root.querySelectorAll('.el-dropdown-menu__item,.el-dropdown-menu__item *,button,.el-button,[role=\"button\"],a').forEach(function(node){"
    "var text=normalizedText(node);"
    "if(!shouldHide(text,managementLabels)){return;}"
    "hideClosest(node,'.el-dropdown-menu__item,button,.el-button,[role=\"button\"],a,li');"
    "});"
    "}"
    "function cleanAddStudent(root){"
    "root.querySelectorAll('*').forEach(function(node){"
    "var text=normalizedText(node);"
    "if(!shouldHide(text,addStudentLabels)){return;}"
    "hideClosest(node,'.el-form-item,.el-dropdown-menu__item,.el-button,.el-col,.el-row,li,div');"
    "});"
    "}"
    "function clean(){"
    "var path=location.pathname||'';"
    "var root=document.body||document.documentElement;"
    "if(!root||!root.querySelectorAll){return;}"
    "if(studentListPath.test(path)){cleanManagement(root);return;}"
    "if(addStudentPath.test(path)){cleanAddStudent(root);}"
    "}"
    "function schedule(){clean();}"
    "if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',schedule,{once:true});}else{schedule();}"
    "new MutationObserver(function(){schedule();}).observe(document.documentElement,{childList:true,subtree:true});"
    "}());"
    "</script>"
)
LEGACY_ISPRING_TEXT_LAYOUT_GUARD = (
    "<script>"
    "(function(){"
    "if(window.__localLegacyIspringTextGuard){return;}"
    "window.__localLegacyIspringTextGuard=true;"
    "function shouldPatch(node){"
    "if(!node||!node.parentElement||!node.matches||!node.matches('span[id^=\"txt\"]')){return false;}"
    "var style=window.getComputedStyle(node);"
    "if(style.position!=='absolute'||style.whiteSpace==='nowrap'){return false;}"
    "var parent=node.parentElement;"
    "var parentStyle=window.getComputedStyle(parent);"
    "if(parentStyle.width!=='0px'&&parent.getBoundingClientRect().width>1){return false;}"
    "var declaredWidth=parseFloat(node.getAttribute('data-width')||'0');"
    "if(!(declaredWidth>0)){return false;}"
    "var rect=node.getBoundingClientRect();"
    "if(rect.width>=declaredWidth*0.75){return false;}"
    "var lineHeight=parseFloat(style.lineHeight)||0;"
    "if(lineHeight>0&&rect.height<=lineHeight*1.6){return false;}"
    "return true;"
    "}"
    "function patchNode(node){"
    "if(!shouldPatch(node)){return;}"
    "node.parentElement.style.whiteSpace='nowrap';"
    "node.style.whiteSpace='nowrap';"
    "}"
    "function patchTree(root){"
    "if(!root||root.nodeType!==1){return;}"
    "patchNode(root);"
    "if(!root.querySelectorAll){return;}"
    "root.querySelectorAll('span[id^=\"txt\"]').forEach(patchNode);"
    "}"
    "var scheduled=false;"
    "function scheduleScan(){"
    "if(scheduled){return;}"
    "scheduled=true;"
    "requestAnimationFrame(function(){"
    "scheduled=false;"
    "if(document.body){patchTree(document.body);}"
    "});"
    "}"
    "if(document.readyState==='loading'){"
    "document.addEventListener('DOMContentLoaded',scheduleScan,{once:true});"
    "}else{"
    "scheduleScan();"
    "}"
    "window.addEventListener('load',scheduleScan);"
    "window.addEventListener('resize',scheduleScan);"
    "if(document.fonts&&document.fonts.ready&&document.fonts.ready.then){"
    "document.fonts.ready.then(scheduleScan).catch(function(){});"
    "}"
    "new MutationObserver(function(mutations){"
    "for(var i=0;i<mutations.length;i+=1){"
    "var mutation=mutations[i];"
    "for(var j=0;j<mutation.addedNodes.length;j+=1){"
    "patchTree(mutation.addedNodes[j]);"
    "}"
    "}"
    "scheduleScan();"
    "}).observe(document.documentElement,{childList:true,subtree:true});"
    "}());"
    "</script>"
)

# Defensive frontend guard for non-core dashboard widget endpoints.
# - Patches fetch + XMLHttpRequest so non-core widget URLs always return a clean
#   empty success payload, regardless of what the upstream API actually returned.
# - Replaces the default <el-empty> illustration/text with a localized
#   "本模块未启用" placeholder so widgets render with consistent UX.
NON_CORE_DASHBOARD_WIDGET_GUARD = (
    "<script>"
    "(function(){"
    "if(window.__localNonCoreDashboardGuard){return;}"
    "window.__localNonCoreDashboardGuard=true;"
    "var nonCorePaths=["
    "'/java-api/school/intend/board/soa',"
    "'/java-api/school/intend/board/echarts/stat',"
    "'/java-api/school/intend/selectList',"
    "'/java-api/school/stu/board/recSoa',"
    "'/java-api/school/stu/board/incomeSoa',"
    "'/java-api/school/stu/board/echarts/recStat',"
    "'/java-api/school/stu/board/echarts/consumeStat',"
    "'/java-api/school/tch/board/recordSoa',"
    "'/java-api/school/tch/board/echarts/recordStat',"
    "'/java-api/school/visitRecord/selectList',"
    "'/java-api/school/tchPlan/exportSignRecord',"
    "'/api/get/base/meterial/scene/list',"
    "'/api/get/base/meterial/list',"
    "'/api/get/editorRemark',"
    "'/api/get/intended/student/list/by/real/come/date'"
    "];"
    "var emptyPayload=JSON.stringify({"
    "success:true,"
    "content:{list:[],total:0,size:0,current:1,pages:1},"
    "error:{message:'',code:''}"
    "});"
    "function isNonCore(url){"
    "if(!url){return false;}"
    "for(var i=0;i<nonCorePaths.length;i+=1){"
    "if(url.indexOf(nonCorePaths[i])!==-1){return true;}"
    "}"
    "return false;"
    "}"
    "function makeEmptyResponse(){"
    "return new Response(emptyPayload,{"
    "status:200,"
    "statusText:'OK',"
    "headers:{'Content-Type':'application/json; charset=utf-8'}"
    "});"
    "}"
    "if(window.fetch&&!window.__localNonCoreFetchPatched){"
    "window.__localNonCoreFetchPatched=true;"
    "var origFetch=window.fetch.bind(window);"
    "window.fetch=function(input,init){"
    "var url=(typeof input==='string')?input:(input&&input.url)||'';"
    "if(isNonCore(url)){"
    "return Promise.resolve(makeEmptyResponse());"
    "}"
    "return origFetch(input,init);"
    "};"
    "}"
    "if(window.XMLHttpRequest&&!window.__localNonCoreXhrPatched){"
    "window.__localNonCoreXhrPatched=true;"
    "var origOpen=XMLHttpRequest.prototype.open;"
    "var origSend=XMLHttpRequest.prototype.send;"
    "XMLHttpRequest.prototype.open=function(method,url){"
    "this.__localNonCoreUrl=url;"
    "return origOpen.apply(this,arguments);"
    "};"
    "XMLHttpRequest.prototype.send=function(){"
    "if(isNonCore(this.__localNonCoreUrl)){"
    "var self=this;"
    "setTimeout(function(){"
    "Object.defineProperty(self,'readyState',{get:function(){return 4;}});"
    "Object.defineProperty(self,'status',{get:function(){return 200;}});"
    "Object.defineProperty(self,'responseText',{get:function(){return emptyPayload;}});"
    "Object.defineProperty(self,'response',{get:function(){return emptyPayload;}});"
    "self.dispatchEvent(new Event('readystatechange'));"
    "self.dispatchEvent(new Event('load'));"
    "},0);"
    "return;"
    "}"
    "return origSend.apply(this,arguments);"
    "};"
    "}"
    "function patchEmptyNodes(){"
    "try{"
    "var nodes=document.querySelectorAll('.el-empty__description p');"
    "for(var i=0;i<nodes.length;i+=1){"
    "var t=(nodes[i].textContent||'').trim();"
    "if((t==='暂无数据'||t==='暂无')&&!nodes[i].__localNonCoreReplaced){"
    "nodes[i].textContent='本模块未启用';"
    "nodes[i].__localNonCoreReplaced=true;"
    "}"
    "}"
    "}catch(e){}"
    "}"
    "if(document.readyState==='loading'){"
    "document.addEventListener('DOMContentLoaded',patchEmptyNodes,{once:true});"
    "}else{patchEmptyNodes();}"
    "setTimeout(patchEmptyNodes,500);"
    "setTimeout(patchEmptyNodes,2000);"
    "new MutationObserver(patchEmptyNodes).observe(document.documentElement,{childList:true,subtree:true});"
    "}());"
    "</script>"
)
POST_LOGIN_REDIRECT_GUARD = (
    "<script>"
    "(function(){"
    "if(window.__localPostLoginRedirectGuard){return;}"
    "window.__localPostLoginRedirectGuard=true;"
    "var targets={"
    "admin:'/background/course-management/school-curriculum',"
    "teacher:'/code-classroom/classroom-index',"
    "student:'/code-classroom/myClass'"
    "};"
    "function normalizePath(path){"
    "path=((path||'')+'').replace(/\\/+$|^$/g,'');"
    "return path?('/'+path.replace(/^\\/+/,'')):'/';"
    "}"
    "function readCookie(name){"
    "var prefix=name+'=';"
    "var parts=(document.cookie||'').split(';');"
    "for(var i=0;i<parts.length;i+=1){"
    "var item=parts[i].trim();"
    "if(item.indexOf(prefix)===0){return decodeURIComponent(item.slice(prefix.length));}"
    "}"
    "return '';"
    "}"
    "function parseVuex(){"
    "try{var raw=localStorage.getItem('vuex')||'';return raw?JSON.parse(raw):{};}catch(e){return {};}"
    "}"
    "function profileToRole(profile){"
    "profile=((profile||'')+'').trim();"
    "if(!profile){return '';}"
    "if(profile==='admin'){return 'admin';}"
    "if(profile==='student'||profile.indexOf('local_student_')===0){return 'student';}"
    "return 'teacher';"
    "}"
    "function resolveRole(){"
    "var role=profileToRole((function(){try{return sessionStorage.getItem('mirror_profile')||'';}catch(e){return '';}})());"
    "if(role){return role;}"
    "role=profileToRole(readCookie('mirror_profile'));"
    "if(role){return role;}"
    "var user=((parseVuex()||{}).user)||{};"
    "if(user.isStudent||Number(user.identity)===2){return 'student';}"
    "if(user.isAdmin){return 'admin';}"
    "if(user.isTeacher||Number(user.identity)===1){return 'teacher';}"
    "return '';"
    "}"
    "function resolveToken(){"
    "var token=((((parseVuex()||{}).user)||{}).token);"
    "if(typeof token==='string'){return token.trim();}"
    "if(token&&typeof token==='object'&&typeof token.token==='string'){return token.token.trim();}"
    "return '';"
    "}"
    "function shouldRedirect(path, role){"
    "var target=targets[role];"
    "if(!target){return false;}"
    "path=normalizePath(path);"
    "if(path===normalizePath(target)){return false;}"
    "return path==='/'||path==='/login'||path==='/background/login';"
    "}"
    "var scheduled=false;"
    "var redirecting=false;"
    "function handleHomeClick(event){"
    "if(redirecting){return;}"
    "var node=event.target;"
    "if(node&&node.nodeType===3){node=node.parentElement;}"
    "if(!node||typeof node.closest!=='function'){return;}"
    "node=node.closest('a,button,li,[role=\"menuitem\"]');"
    "if(!node){return;}"
    "var label=((node.textContent||'')+'').replace(/\\s+/g,'').trim();"
    "if(label!=='首页'&&label!=='返回首页'){return;}"
    "var role=resolveRole();"
    "var target=targets[role];"
    "if(!target||!resolveToken()){return;}"
    "event.preventDefault();"
    "event.stopPropagation();"
    "event.stopImmediatePropagation();"
    "redirecting=true;"
    "window.location.assign(target);"
    "}"
    "function enforce(){"
    "scheduled=false;"
    "if(redirecting){return;}"
    "var role=resolveRole();"
    "var token=resolveToken();"
    "if(!role||!token){return;}"
    "if(!shouldRedirect(location.pathname||'/',role)){return;}"
    "redirecting=true;"
    "window.location.replace(targets[role]);"
    "}"
    "function schedule(){"
    "if(scheduled||redirecting){return;}"
    "scheduled=true;"
    "setTimeout(enforce,0);"
    "}"
    "document.addEventListener('click',handleHomeClick,true);"
    "if(window.Storage&&window.Storage.prototype&&!window.__localStorageSetItemGuard){"
    "window.__localStorageSetItemGuard=true;"
    "var originalSetItem=window.Storage.prototype.setItem;"
    "window.Storage.prototype.setItem=function(key,value){"
    "var result=originalSetItem.apply(this,arguments);"
    "if(key==='vuex'||key==='mirror_profile'){schedule();}"
    "return result;"
    "};"
    "}"
    "if(window.history&&typeof window.history.pushState==='function'&&!window.__localPushStateGuard){"
    "window.__localPushStateGuard=true;"
    "var originalPushState=window.history.pushState;"
    "window.history.pushState=function(){var result=originalPushState.apply(this,arguments);schedule();return result;};"
    "var originalReplaceState=window.history.replaceState;"
    "window.history.replaceState=function(){var result=originalReplaceState.apply(this,arguments);schedule();return result;};"
    "}"
    "window.addEventListener('popstate',schedule);"
    "window.addEventListener('load',schedule);"
    "if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',schedule,{once:true});}else{schedule();}"
    "setTimeout(schedule,250);"
    "setTimeout(schedule,1200);"
    "}());"
    "</script>"
)

FROZEN_CLASSROOM_SNAPSHOT_FALLBACK_AVATAR = (
    '<div class="el-image logo_img">'
    '<img src="/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png" '
    'class="el-image__inner" style="object-fit: cover; border-radius: 50%;">'
    "<!---->"
    "</div>"
)
DEFAULT_HOMEPAGE_AVATAR_URL = "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png"
DEFAULT_HOMEPAGE_MODAL_URL = "/_external/wugecdn.steam.fun/resources/static/homepage/person-icon.jpeg"
STATIC_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}
INLINE_REWRITE_MAX_BYTES = 4 * 1024 * 1024
TRANSPARENT_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc````\x00"
    b"\x00\x00\x05\x00\x01\xa5\xf6E@\x00\x00\x00\x00IEND\xaeB`\x82"
)

# Smallest universally-decodable 1x1 transparent raster (GIF89a). Used as a
# safe fallback for any missing image/* asset (jpeg, gif, webp, bmp) so the
# browser does not raise a "wrong format" decode error.
TRANSPARENT_GIF_BYTES = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff"
    b"\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,"
    b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02"
    b"D\x01\x00;"
)
TEXTUAL_REWRITE_PROBE_BYTES = (
    b"http://",
    b"https://",
    b"e.data.error.message",
    b"e.data.error.code",
    b"e.style[r]=n",
    b'name:"look-curriculum"',
    b'$store.dispatch("LogOut")',
    b'$store.dispatch("AdminLogOut")',
    b"html5-unsupported",
    b"performRedirectIfNeeded",
    b"PB_RESUME_PRESENTATION_WINDOW_TEXT",
    b"window.location.reload()",
    b"/version.json?v=",
)
COURSE_SHARED_DATA_FALLBACK_FILENAMES = frozenset(
    {
        "apple-touch-icon.png",
        "browsersupport.js",
        "favicon.ico",
        "jquery.cokie.min.js",
        "jquery.min.js",
        "ksahdklgjls.js",
        "player.js",
    }
)
TEACHING_PLAN_EMPTY_ENDPOINTS = {
    "/api/tch/getTeachingPlanList": {
        "success": True,
        "content": {"teachingPlan": [], "total": 0, "page_no": 1, "page_size": 20},
        "error": {"message": "", "code": ""},
    },
    "/api/checkLessonHasQuestionBank": {
        "success": True,
        "content": {"has_question_bank": False},
        "error": {"message": "", "code": ""},
    },
}
EMPTY_CPP_PROBLEM_LIST_RESPONSE = {
    "success": True,
    "content": {"cppLessonOjProblemRelationList": []},
    "error": {"message": "", "code": ""},
}
DEFAULT_STAR_RULE_ROWS = [
    {"scene": "上课", "behavior": "上课和老师互动"},
    {"scene": "课堂创作", "behavior": "完成上课创作、课后作业"},
    {"scene": "考试", "behavior": "考试达到标准"},
    {"scene": "点名签到", "behavior": "设置好奖励规则，系统自动发放星币"},
    {"scene": "信奥专区", "behavior": "刷题正确提交"},
    {"scene": "分享学习报告", "behavior": "分享学习报告，获得点赞"},
]
ASSET_PATH_SAFE_CHARS = "!$&'()*+,;=:@-._~"
BENIGN_PLACEHOLDER_ROUTES = {
    "code-classroom/prepare-lessons/prepare/undefined",
    "code-classroom/teach-lessons/lessons/undefined",
}
TEACHER_API_PREFIXES = (
    "/java-api/school/",
    "/java-api/exam/",
    "/api/exam/",
    "/api/get/campus/",
    "/api/get/user/",
    "/api/get/educational_institution_campus/",
    "/api/prepare/",
    "/api/tch",
    "/api/checkLessonHasQuestionBank",
    "/api/tchWorkSelfRemark",
)
STUDENT_API_PREFIXES = ("/java-api/student/", "/api/stu/")
PLACEHOLDER_NAME_CHARS = frozenset({"?"})
DEFAULT_BOUND_TEXT = "Bound"
DEFAULT_UNBOUND_TEXT = "Unbound"
STUDENT_OVERLAY_FIELD_ALIASES = {
    "normal_state": ("normalState", "normal_state", "accountState"),
    "end_date": ("endDate", "end_date", "studyDate", "study_date"),
    "zone_auth": ("zoneAuth", "zone_auth"),
    "test_auth": ("testAuth", "test_auth"),
    "oj_auth": ("ojAuth", "oj_auth"),
    "oj_analysis_auth": ("ojAnalysisAuth", "oj_analysis_auth"),
    "oj_testcase_auth": ("ojTestcaseAuth", "oj_testcase_auth"),
    "stu_note_auth": ("stuNoteAuth", "stu_note_auth"),
    "p_auth": ("pAuth", "p_auth"),
    "wechat_bound": ("wechatBound", "wechat_bound"),
    "parent_wechat": ("parentWeChat", "parent_wechat"),
    "wcm_flag": ("wcmFlag", "wcm_flag"),
    "open_id": ("openId", "open_id"),
    "authorizer_openid": ("authorizerOpenid", "authorizer_openid"),
}
TEACHER_CLASSROOM_ROOT_ROUTES = {
    "/code-classroom/prepare-lessons",
    "/code-classroom/teach-lessons",
    "/code-classroom/myClass",
}
TEACHER_SESSION_ROOT_ROUTES = {
    "/code-classroom/prepare-lessons",
    "/code-classroom/teach-lessons",
}
TEACHER_COMPETITION_ROUTE_PREFIXES = (
    "/competitionCenter",
    "/exam",
    "/exam-stu",
    "/exam-management",
    "/practice-management",
)
NON_CORE_FRONTEND_ROUTE_PREFIXES = (
    "/competitionCenter",
    "/exam",
    "/exam-stu",
    "/exam-management",
    "/practice-management",
)
NON_CORE_ADMIN_FRONTEND_ROUTES = {
    "/background/course-management/platform-curriculum",
}
DEFAULT_TEACHER_SUBJECT_ROWS = (
    {
        "id": 1,
        "code": 1,
        "name": "Jrcode",
        "sort_num": 1,
        "state": 1,
        "is_vaild": True,
        "color": "#FFF2F2",
        "font_color": "#950B0B",
    },
    {
        "id": 2,
        "code": 2,
        "name": "Scratch",
        "sort_num": 2,
        "state": 1,
        "is_vaild": True,
        "color": "#E8EDFB",
        "font_color": "#224CDA",
    },
    {
        "id": 3,
        "code": 3,
        "name": "Python",
        "sort_num": 3,
        "state": 1,
        "is_vaild": True,
        "color": "#EAFBF0",
        "font_color": "#0A7A33",
    },
    {
        "id": 4,
        "code": 4,
        "name": "C++",
        "sort_num": 4,
        "state": 1,
        "is_vaild": True,
        "color": "#FFF4E8",
        "font_color": "#A55400",
    },
)
LOCAL_TEACHER_FALLBACK_PATHS = {
    "/api/admin/fresh/auth/user/data",
    "/api/admin/get/auth/user/list",
    "/api/admin/get/auth/user/info",
    "/api/admin/add/or/update/auth/user",
    "/api/admin/delete/auth/user",
    "/api/admin/auth/user/update/password",
    "/api/get/educational_institution_campus/list",
    "/api/get/campus/arr/subject/list",
    "/api/get/campus/user/list",
    "/api/get/user/campus/list",
    "/api/get/homepage",
    "/api/get/teaching/plan/list",
    "/api/get/campus/subject/list",
    "/api/get/school/subject/list",
    "/api/get/zone/school/subject/list",
    "/api/get/all/campus/all/curriculum/title/list",
    "/api/get/campus/curriculum/list/by/page",
    "/api/get/curriculum/list",
    "/api/get/curriculum",
    "/api/get/school/file/list",
    "/api/get/school/board/main/data",
    "/api/tch/get/tch/curriculum",
    "/api/tch/get/tch/subject/auth",
    "/api/tch/getTchIndexClassListWithTchPlanInfo",
    "/api/tch/get/teaching/plan/list",
    "/api/tch/get/stu/tch/plan/list/by/tch/id",
    "/api/tch/getTchPlanListForEvaluate",
    "/api/tch/getStuTchPlanListForEvaluate",
    "/api/getTeachingPlanStuListWithXmArr",
    "/api/get/classes/list",
    "/api/get/class/student/list",
    "/api/get/teaching/plan/by/class/id",
    "/api/tch/class/get/classlist",
    "/api/get/educational_institution_info",
    "/api/get/tch/lesson/work",
    "/api/get/tch/lesson/work/list",
    "/api/get/tch/training/list",
    "/api/get/tch/training/info",
    "/api/admin/get/tch/training/list",
    "/api/admin/get/tch/training/info",
    "/api/tch/get/stu/lesson/tch/work/list",
    "/api/tch/get/tch/stu/tch/work/list",
    "/api/tch/xmedu/getSchoolOpenMissClass",
    "/api/tch/xmedu/getSchoolOpenMissClassOfTeachingPlan",
    "/api/test/school/question/bank/auth",
    "/api/get/school/banner/list",
    "/api/exam/get/school/exam/list",
    "/api/exam/getSchoolLessonExamList",
    "/api/exam/getKeepPaperList",
    "/api/exam/get/school/question/bank/list",
    "/api/exam/getBankSourceInfo",
    "/api/exam/getTestQuestionBankSourceTagListWithoutPage",
    "/api/admin/get/latest/sys/total/info",
    "/api/admin/get/school/num/by/school/subject",
    "/api/admin/get/stu/num/by/subject",
    "/api/getSubjectAndCurriculumListForClassAddLesson",
    "/api/getSubject",
    "/api/xm/getXmOrderList",
    "/api/xm/getStuInfoForFinacialPages",
    "/api/xm/getXmAccountInfoByStuId",
    "/api/get/receipt/charge/goods/list",
    "/api/get/receipt/account/list",
    "/api/getHeaderSet",
    "/java-api/points/sch/order/queryList",
    "/java-api/auth/sch/eduRole/queryListNoCheck",
    "/java-api/points/tch/ruleTag/check",
    "/java-api/school/lessonHourRecord/selectLessonCost",
    "/java-api/school/orderPayRecord/selectOrderPayDetail",
    "/java-api/school/tch/common/selectByEduCampusId",
    "/java-api/school/tch/verifyPhoneState",
    "/java-api/school/tch/checkPwd",
    "/java-api/school/community/work/queryStuWorkList",
    "/java-api/school/tch/employeeSetting/resetWeMiniOpenid",
    "/java-api/school//tch/employeeSetting/resetWeMiniOpenid",
    "/java-api/school/tch/employeeSetting/selectEmployList",
    "/java-api/school/edu/campus/selectEduCampusTchList",
    "/api/get/school/right/info",
    "/java-api/school/stu/setEndDate",
    "/java-api/school/stu/batchSetEndDate",
    "/java-api/school/currCls/countSignedTchPlan",
    "/java-api/school/tch/selectCurrCls",
    "/java-api/exam/sch/testExamStu/getList",
    "/java-api/exam/sch/testExamStu/getPracticeRecords",
    "/java-api/exam/sch/testExamStu/getExamRecords",
    "/java-api/exam/sch/testExamStu/getScoreRankList",
    "/java-api/exam/sch/testStuWrongQuestion/statistics",
    "/java-api/exam/sch/testStuWrongQuestion/list",
    "/java-api/exam/sch/testExam/detail",
    "/java-api/exam/sch/testStuWrongQuestion/guide",
    "/java-api/exam/sch/testExam/questionAnalysis",
    "/java-api/exam/sch/testExam/practiceDetail",
    "/java-api/exam/sch/testStuWrongQuestion/practiceGuide",
    "/java-api/exam/sch/testExam/practiceAnalysis",
    "/java-api/school/stu/queryTimeRecord",
    "/java-api/exam/sch/testExam/getQuestionTypesAndSubjects",
    "/java-api/school/xmAccountStu/queryAccountList",
    "/java-api/school/currCls/delete",
    "/java-api/school/currMat/detail",
    "/java-api/school/edu/campus/queryListByUserId",
    "/api/get/tch/notice/list/for/school/board",
    "/java-api/school/visitRecord/selectList",
    "/api/getTchRecentNotReadNotice",
    "/java-api/school/edu/getPlatformRights",
    "/api/update/updateAllNoticeRead",
}
LOCAL_TEACHER_PREFER_LOCAL_FALLBACK_PATHS = {
    "/api/admin/fresh/auth/user/data",
    "/api/admin/get/auth/user/list",
    "/api/admin/get/auth/user/info",
    "/api/admin/add/or/update/auth/user",
    "/api/admin/delete/auth/user",
    "/api/admin/auth/user/update/password",
    "/api/get/educational_institution_campus/list",
    "/api/get/campus/arr/subject/list",
    "/api/get/campus/user/list",
    "/api/get/school/board/main/data",
    "/api/get/user/campus/list",
    "/api/get/teaching/plan/list",
    "/api/tch/get/teaching/plan/list",
    "/api/tch/get/tch/subject/auth",
    "/api/tch/getTchIndexClassListWithTchPlanInfo",
    "/api/tch/get/stu/tch/plan/list/by/tch/id",
    "/api/get/class/student/list",
    "/api/get/tch/lesson/work/list",
    "/api/tch/get/stu/lesson/tch/work/list",
    "/api/tch/get/tch/stu/tch/work/list",
    "/java-api/points/sch/eduCampus/starRule",
    "/java-api/points/stu/eduCampus/starRule",
    "/java-api/auth/sch/eduRole/queryListNoCheck",
    "/java-api/points/tch/ruleTag/check",
    "/java-api/school/community/work/queryStuWorkList",
    "/java-api/school/tch/employeeSetting/resetWeMiniOpenid",
    "/java-api/school//tch/employeeSetting/resetWeMiniOpenid",
    "/java-api/school/tch/employeeSetting/selectEmployList",
    "/java-api/school/tch/verifyPhoneState",
    "/java-api/school/tch/checkPwd",
    "/java-api/school/edu/campus/selectEduCampusTchList",
    "/api/get/school/right/info",
    "/java-api/exam/sch/testExamStu/getPracticeRecords",
    "/java-api/exam/sch/testExamStu/getExamRecords",
    "/java-api/exam/sch/testExamStu/getScoreRankList",
    "/java-api/exam/sch/testStuWrongQuestion/statistics",
    "/java-api/exam/sch/testStuWrongQuestion/list",
    "/java-api/exam/sch/testExam/detail",
    "/java-api/exam/sch/testStuWrongQuestion/guide",
    "/java-api/exam/sch/testExam/questionAnalysis",
    "/java-api/exam/sch/testExam/practiceDetail",
    "/java-api/exam/sch/testStuWrongQuestion/practiceGuide",
    "/java-api/exam/sch/testExam/practiceAnalysis",
    "/java-api/school/stu/queryTimeRecord",
    "/api/getSubjectAndCurriculumListForClassAddLesson",
    "/api/getSubject",
    "/api/xm/getStuInfoForFinacialPages",
    "/api/xm/getXmAccountInfoByStuId",
    "/api/get/receipt/charge/goods/list",
    "/api/get/receipt/account/list",
    "/java-api/school/xmAccountStu/queryAccountList",
    "/java-api/school/currCls/delete",
    "/java-api/school/currMat/detail",
    "/java-api/school/edu/campus/queryListByUserId",
    "/api/get/tch/notice/list/for/school/board",
    "/java-api/school/visitRecord/selectList",
    "/api/getTchRecentNotReadNotice",
}
LOCAL_STUDENT_FALLBACK_PATHS = {
    "/api/get/homepage",
    "/api/stu/get/indexinfo/for/new",
    "/api/stu/get/index/tch/work/list",
    "/api/stu/get/stu/subject/auth",
    "/api/stu/get/stu/work/subject",
    "/api/stu/get/tch/work/list",
    "/api/stu/get/stu/class/list",
    "/api/get/user/campus/list",
    "/api/tch/get/tch/subject/auth",
    "/api/tch/getTchIndexClassListWithTchPlanInfo",
    "/api/tch/class/get/classlist",
    "/api/stu/get/stu/tch/plan/list",
    "/api/stu/get/stu/timetable",
    "/api/stu/get/stu/timetable/new",
    "/api/stu/getStuTimetableNewWithOutPageInfo",
    "/java-api/student/stu/checkPwd",
    "/java-api/student/stu/getStuPwdRemind",
}
LOCAL_STUDENT_PREFER_LOCAL_FALLBACK_PATHS = set(LOCAL_STUDENT_FALLBACK_PATHS)
LOCAL_STUDENT_PREFER_LOCAL_FALLBACK_PATHS.update(
    {
        "/java-api/points/sch/eduCampus/starRule",
        "/java-api/points/stu/eduCampus/starRule",
    }
)
LOCAL_STU_EXAM_PATHS = {
    "/api/stuexam/get/stu/exam/list",
    "/api/stuexam/getStuLessonExamList",
    "/api/stuexam/get/stu/exam/question/list",
    "/api/stuexam/check/single/question",
    "/api/stuexam/get/stu/question/answer",
    "/api/stuexam/submit/paper",
    "/api/stuexam/get/stu/practice/list",
    "/api/stuexam/get/exam/result/question/list",
    "/api/stuexam/getStuWrongQuestionListForNew",
}
# Dashboard widget APIs that the SPA still calls but are explicitly out of scope
# for the minimal local build. We intercept them at the very top of replay_api
# (before any DB lookup) so they always return a clean empty success payload,
# preventing 404 noise on the admin/teacher dashboards.
NON_CORE_DASHBOARD_API_PATHS: frozenset[str] = frozenset(
    {
        # Sales / visit record (leads tracking)
        # Teaching-plan roll-call export (out-of-scope in minimal build)
        "/java-api/school/tchPlan/exportSignRecord",
        # Material scene list / search (curriculum picker extras)
        "/api/get/base/meterial/scene/list",
        "/api/get/base/meterial/list",
        "/api/get/editorRemark",
        "/api/get/intended/student/list/by/real/come/date",
    }
)


def _non_core_dashboard_empty_response() -> Response:
    # Return a structured empty success payload for dashboard widget endpoints.
    # Matches the JSON shape the SPA expects so widgets render an empty/zero state
    # instead of showing error toasts on pages we deliberately do not support.
    return JSONResponse(
        {
            "success": True,
            "content": {
                "list": [],
                "total": 0,
                "size": 0,
                "current": 1,
                "pages": 1,
            },
            "error": {"message": "", "code": ""},
        },
        status_code=200,
    )

CORE_BACKGROUND_ROUTE_PREFIX = "/background/course-management"
CORE_BACKGROUND_ALLOWED_SUBMENUS = ("教务中心", "课程中心")
CORE_BACKGROUND_ALLOWED_MENU_ITEMS = ("学员管理", "班级管理", "教学计划", "课程管理")
CORE_BACKGROUND_ALLOWED_PERMISSION_CHILDREN: dict[str, tuple[str, ...]] = {
    "tchCenter": ("students-management1", "class-management1", "teachplan1"),
    "courseCenter": ("course-list",),
}
LOCAL_TEACHER_FALLBACK_PATHS.update(LOCAL_STU_EXAM_PATHS)
LOCAL_TEACHER_PREFER_LOCAL_FALLBACK_PATHS.update(LOCAL_STU_EXAM_PATHS)
LOCAL_STUDENT_FALLBACK_PATHS.update(LOCAL_STU_EXAM_PATHS)
LOCAL_STUDENT_PREFER_LOCAL_FALLBACK_PATHS.update(LOCAL_STU_EXAM_PATHS)
SUMMER_WATERMELON_WORK_DIR = "Jrcode_202505_SummerWatermelon"
SUMMER_WATERMELON_LOCAL_WORK_DIR = "Jrcode_202505_SQ"
MISSING_SVG_LIBRARY_ALIASES = {
    "jrcode/svglibrary/Crocodile01.svg": "jrcode/svglibrary/Crocodile05.svg",
    "jrcode/svglibrary/Crocodile02.svg": "jrcode/svglibrary/Crocodile05.svg",
}
SVG_LIBRARY_PLACEHOLDER_PREFIX = "jrcode/svglibrary/"
EXTERNAL_ROOT_LANDING_PATHS = ("index", "index.html", "home", "cms")
TRANSPARENT_PNG_PLACEHOLDER_PREFIXES = (
    "img/clickDownload",
    "img/play@2x.",
    "img/rankingPodium@2x.",
    "img/rankingTitle@2x.",
)
COURSE_POSTER_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
COURSE_DATA_THUMBNAIL_PATTERN = re.compile(r"^th(?:mb|b)\d+\.(?:png|jpe?g)$", re.IGNORECASE)


def _is_textual_content_type(content_type: str) -> bool:
    return any(marker in content_type.lower() for marker in TEXTUAL_RESPONSE_MARKERS)


def _sniff_local_media_type(path: Path, body: bytes) -> str | None:
    stripped = body.lstrip()
    if not stripped:
        return None

    lowered = stripped[:1024].lower()
    if lowered.startswith((b"<!doctype html", b"<html")) or b"<html" in lowered:
        return "text/html"
    if lowered.startswith(b"<svg") or b"<svg" in lowered:
        return "image/svg+xml"
    if lowered.startswith(b"<?xml"):
        return "application/xml"
    if stripped.startswith((b"{", b"[")):
        return "application/json"
    if path.name in EXTERNAL_ROOT_LANDING_PATHS and b"<body" in lowered:
        return "text/html"
    return None


def _requested_asset_suffix(expected_asset_path: str | None) -> str:
    if not expected_asset_path:
        return ""
    return Path(expected_asset_path).suffix.lower()


def _is_mislabeled_html_asset(path: Path, expected_asset_path: str | None) -> bool:
    if _requested_asset_suffix(expected_asset_path) not in {".js", ".css"}:
        return False
    try:
        with path.open("rb") as handle:
            probe = handle.read(1024)
    except OSError:
        return False
    return _sniff_local_media_type(path, probe) == "text/html"


def _sanitize_outbound_headers(headers: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in headers.items() if key.lower() not in HOP_BY_HOP_HEADERS}


def _get_header(headers: dict[str, Any], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return str(value)
    return None


def _decode_body(body: bytes, headers: dict[str, Any]) -> bytes:
    encoding = (_get_header(headers, "content-encoding") or "").lower()
    if not encoding:
        return body

    decoded = body
    for part in reversed([item.strip() for item in encoding.split(",") if item.strip()]):
        try:
            if part == "br":
                decoded = brotli.decompress(decoded)
            elif part == "gzip":
                decoded = gzip.decompress(decoded)
            elif part == "deflate":
                decoded = zlib.decompress(decoded)
        except Exception:
            return body
    return decoded


def _body_might_need_rewrite(body: bytes, content_type: str) -> bool:
    lowered = content_type.lower()
    if "html" in lowered:
        return True
    return any(needle in body for needle in TEXTUAL_REWRITE_PROBE_BYTES)


def _maybe_rewrite_body(body: bytes, content_type: str, headers: dict[str, Any] | None = None) -> bytes:
    if headers:
        body = _decode_body(body, headers)
    if not _is_textual_content_type(content_type):
        return body
    if len(body) > INLINE_REWRITE_MAX_BYTES:
        return body
    if not _body_might_need_rewrite(body, content_type):
        return body
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = body.decode("utf-8", errors="ignore")
        except MemoryError:
            return body
    except MemoryError:
        return body
    try:
        text = rewrite_external_urls(text)
        return _patch_known_frontend_runtime(text, content_type).encode("utf-8")
    except MemoryError:
        return body


def _patch_known_frontend_runtime(text: str, content_type: str) -> str:
    if "html" in content_type.lower():
        return _inject_runtime_guards(text)
    if "javascript" not in content_type.lower():
        return text
    for needle, replacement in KNOWN_FRONTEND_BUNDLE_REPAIRS.items():
        text = text.replace(needle, replacement)
    if "html5-unsupported" in text and "performRedirectIfNeeded" not in text:
        text = text.replace(*COURSE_BROWSER_SUPPORT_REDIRECT)
    if "PB_RESUME_PRESENTATION_WINDOW_TEXT" in text:
        for needle, replacement in COURSE_PLAYER_DISABLE_RESUME_PROMPT_PATCHES:
            text = text.replace(needle, replacement)
    for needle, replacement in KNOWN_FRONTEND_RUNTIME_PATCHES.items():
        text = text.replace(needle, replacement)
    if 'name:"look-curriculum"' in text:
        def _rewrite_admin_preview_to_local_ppt(match: re.Match[str]) -> str:
            material_var = match.group(1)
            return (
                "(function(material){"
                "if(!material||!material.id){return;}"
                'window.location.assign("/code-classroom/prepare-lessons/prepare/ppt?curriculumMaterial_id="+encodeURIComponent(material.id)+"&teaching_plan_id=999999");'
                f"}})({material_var})"
            )

        text = ADMIN_PREVIEW_TO_LOCAL_PPT_PATTERN.sub(_rewrite_admin_preview_to_local_ppt, text)
    text = VERSION_RELOAD_PATTERN.sub(r'e&&"\1"!=e.version&&void 0', text)
    text = SPA_LOGOUT_PATTERN.sub(
        'this.$store.dispatch("LogOut").then(()=>{window.location.assign("/logout")})',
        text,
    )
    text = ADMIN_SPA_LOGOUT_PATTERN.sub(
        'this.$store.dispatch("AdminLogOut").then(()=>{window.location.assign("/logout")})',
        text,
    )
    return text


def _inject_runtime_guards(text: str) -> str:
    guard_block = ""
    if EMPTY_REJECTION_GUARD not in text:
        guard_block += EMPTY_REJECTION_GUARD
    if GLOBAL_FCN_GUARD not in text:
        guard_block += GLOBAL_FCN_GUARD
    if EDITOR_OPEN_TYPE_GUARD not in text:
        guard_block += EDITOR_OPEN_TYPE_GUARD
    if CLASSROOM_PPT_LAYOUT_GUARD not in text:
        guard_block += CLASSROOM_PPT_LAYOUT_GUARD
    if STUDENT_MYCLASS_LAYOUT_GUARD not in text:
        guard_block += STUDENT_MYCLASS_LAYOUT_GUARD
    if TEACHER_CLASSROOM_INDEX_LAYOUT_GUARD not in text:
        guard_block += TEACHER_CLASSROOM_INDEX_LAYOUT_GUARD
    if CLASSROOM_LOADING_FEEDBACK_GUARD not in text:
        guard_block += CLASSROOM_LOADING_FEEDBACK_GUARD
    if CORE_STUDENT_UI_CLEANUP_GUARD_V2 not in text:
        guard_block += CORE_STUDENT_UI_CLEANUP_GUARD_V2
    if LEGACY_ISPRING_TEXT_LAYOUT_GUARD not in text:
        guard_block += LEGACY_ISPRING_TEXT_LAYOUT_GUARD
    if POST_LOGIN_REDIRECT_GUARD not in text:
        guard_block += POST_LOGIN_REDIRECT_GUARD
    if not guard_block:
        return text
    if "</head>" in text:
        return text.replace("</head>", f"{guard_block}</head>", 1)
    if "<body" in text:
        return text.replace("<body", f"{guard_block}<body", 1)
    return f"{guard_block}{text}"


def _prune_core_background_menu(text: str) -> str:
    allowed_submenus = ("教务中心", "课程中心")
    allowed_menu_items = ("学员管理", "班级管理", "教学计划", "课程管理")
    banned_terms = ("前台业务", "招生运营", "线索管理", "财务中心", "星币管理", "报表分析", "系统设置")
    if not any(term in text for term in banned_terms):
        return text
    for blocked in banned_terms:
        text = re.sub(
            rf"<li\b(?=[^>]*role=[\"']menuitem[\"'])[^>]*class=[\"'][^\"']*(?:el-submenu|el-menu-item)[^\"']*[\"'][^>]*>.*?{re.escape(blocked)}.*?</li>",
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
    for allowed in allowed_submenus:
        text = re.sub(
            rf"(<li\b(?=[^>]*role=[\"']menuitem[\"'])[^>]*class=[\"'][^\"']*el-submenu[^\"']*[\"'][^>]*>.*?{re.escape(allowed)}.*?</li>)",
            lambda match: match.group(1),
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
    for allowed in allowed_menu_items:
        text = re.sub(
            rf"(<li\b(?=[^>]*role=[\"']menuitem[\"'])[^>]*class=[\"'][^\"']*el-menu-item[^\"']*[\"'][^>]*>.*?{re.escape(allowed)}.*?</li>)",
            lambda match: match.group(1),
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
    return text


def _normalize_success_json(body: bytes, content_type: str) -> bytes:
    if "json" not in content_type.lower():
        return body
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        return body
    if not isinstance(payload, dict):
        return body
    if payload.get("success") is True:
        if not isinstance(payload.get("error"), dict):
            payload["error"] = {"message": "", "code": ""}
        content = payload.get("content")
        if isinstance(content, dict):
            content = _normalize_success_content(content)
            payload["content"] = content
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _normalize_success_content(content: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_xm_goods_list_fields(content)
    return normalized if isinstance(normalized, dict) else content


def _normalize_xm_goods_list_fields(value: Any) -> Any:
    if isinstance(value, dict):
        normalized = {key: _normalize_xm_goods_list_fields(item) for key, item in value.items()}
        xm_goods_list = normalized.get("xmGoodsList")
        if "xmGoodsList" in normalized and not isinstance(xm_goods_list, list):
            if xm_goods_list in (None, ""):
                normalized["xmGoodsList"] = []
            elif isinstance(xm_goods_list, tuple):
                normalized["xmGoodsList"] = list(xm_goods_list)
            elif isinstance(xm_goods_list, list):
                normalized["xmGoodsList"] = xm_goods_list
            else:
                normalized["xmGoodsList"] = [xm_goods_list]
        return normalized
    if isinstance(value, list):
        return [_normalize_xm_goods_list_fields(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_xm_goods_list_fields(item) for item in value]
    return value


def _record_contains_invalid_token(record: dict[str, Any] | None) -> bool:
    if not record:
        return False
    if "json" not in str(record.get("content_type") or "").lower():
        return False
    try:
        body = _decode_body(record.get("body") or b"", record.get("headers") or {})
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        return False
    if not isinstance(payload, dict):
        return False

    error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
    content = payload.get("content") if isinstance(payload.get("content"), dict) else {}
    error_code = str(error.get("code") or content.get("code") or "")
    error_message = str(error.get("message") or content.get("message") or "")
    stale_auth_messages = {
        "Remote login detected",
        "Permission verification failed",
        "Unexpected error, please contact the administrator",
        "Frontend users cannot access backend data",
        "Current user is not allowed in this system",
    }
    return error_code == "InvalidToken" or error_message in stale_auth_messages


def _record_has_unsuccessful_json_payload(record: dict[str, Any] | None) -> bool:
    if not record:
        return False
    if "json" not in str(record.get("content_type") or "").lower():
        return False
    try:
        body = _decode_body(record.get("body") or b"", record.get("headers") or {})
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        return False
    if not isinstance(payload, dict):
        return False
    return payload.get("success") is False


def _normalized_frontend_redirect_target(store: MirrorStore, request: Request) -> str | None:
    path = _normalize_route_path(request.url.path)
    if path == "/school-home-page/class-management1/divide-class1":
        existing_keys = {key for key, _ in parse_qsl(request.url.query, keep_blank_values=True)}
        query_pairs = parse_qsl(request.url.query, keep_blank_values=True)
        class_row: dict[str, Any] = {}
        class_id = _extract_class_id_from_request(request)
        if class_id is not None:
            found_class = store.find_class(class_id)
            if isinstance(found_class, dict):
                class_row = found_class
        changed = False
        if "is_cost_lesson_hour" not in existing_keys:
            raw_cost_mode = class_row.get("is_cost_lesson_hour")
            is_cost_mode = str(raw_cost_mode).strip().lower() in {"1", "true", "yes", "on"}
            query_pairs.append(("is_cost_lesson_hour", "true" if is_cost_mode else "false"))
            changed = True
        if "curriculum_class_type" not in existing_keys:
            class_type = _coerce_int(class_row.get("curriculum_class_type")) or 1
            query_pairs.append(("curriculum_class_type", str(class_type)))
            changed = True
        if changed:
            return f"{path}?{urlencode(query_pairs)}"
    if path == "/school-home-page/class-management1/class-management1":
        query = request.url.query
        return f"/school-home-page/class-management1?{query}" if query else "/school-home-page/class-management1"
    return None


def _non_core_frontend_redirect_target(store: MirrorStore, request: Request, route_key: str) -> str | None:
    path = _normalize_route_path(route_key)
    if path in NON_CORE_ADMIN_FRONTEND_ROUTES:
        return _default_frontend_route_for_role("admin")

    is_non_core = False
    for prefix in NON_CORE_FRONTEND_ROUTE_PREFIXES:
        if path == prefix or path.startswith(f"{prefix}/"):
            is_non_core = True
            break
    if not is_non_core:
        return None

    resolved_profile = _resolve_profile(store, request)
    profile_name = resolved_profile["profile_name"] if resolved_profile else _resolve_profile_name(store, request)
    profile_role = _profile_role(profile_name, resolved_profile)
    if profile_role:
        return _default_frontend_route_for_role(profile_role)
    if path == "/exam-stu" or path.startswith("/exam-stu/"):
        return _default_frontend_route_for_role("student")
    return _default_frontend_route_for_role("teacher")


def _sanitize_frozen_classroom_snapshot(text: str) -> str:
    text = MESSAGE_BOX_WRAPPER_RE.sub("", text)
    text = MODAL_BACKDROP_RE.sub("", text)
    return LOGO_IMAGE_ERROR_RE.sub(FROZEN_CLASSROOM_SNAPSHOT_FALLBACK_AVATAR, text)


def _normalize_auth_token(value: str | None) -> str | None:
    if not value:
        return None
    token = value.strip()
    if token.lower().startswith("bearer "):
        return token.split(" ", 1)[1].strip()
    return token


def _hash_login_password(value: Any) -> str:
    return base64.b64encode(hashlib.md5(str(value or "").encode("utf-8")).digest()).decode("ascii")


def _decode_base64_text(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        decoded = base64.b64decode(text, validate=False)
    except Exception:
        return None
    try:
        decoded_text = decoded.decode("utf-8")
    except Exception:
        return None
    if not decoded_text:
        return None
    if any(ord(character) < 32 and character not in "\t\r\n" for character in decoded_text):
        return None
    return decoded_text


def _looks_like_password_hash(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        decoded = base64.b64decode(text, validate=True)
    except Exception:
        return False
    return len(decoded) == 16


def _normalize_local_password_hash(value: Any, *, fallback: str | None = None) -> str:
    text = str(value or "").strip()
    if not text:
        if fallback:
            return fallback
        return _hash_login_password("123456")
    decoded_text = _decode_base64_text(text)
    if decoded_text is not None:
        return _hash_login_password(decoded_text)
    if _looks_like_password_hash(text):
        return text
    return _hash_login_password(text)


def _normalized_optional_filter_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.lower() in {"all", "null", "none", "-1"}:
        return ""
    if "?" in text or "�" in text:
        return ""
    return text


def _json_response(payload: dict[str, Any], status_code: int = 200) -> JSONResponse:
    return JSONResponse(payload, status_code=status_code)


def _success_payload(content: Any) -> dict[str, Any]:
    return {"success": True, "content": content, "error": {"message": "", "code": ""}}


def _local_json_record(payload: dict[str, Any], *, status: int = 200) -> dict[str, Any]:
    content_type = "application/json; charset=utf-8"
    return {
        "status": status,
        "content_type": content_type,
        "headers": {"content-type": content_type},
        "body": json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    }


def _empty_page_content(
    page_no: int,
    page_size: int,
    *list_keys: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    content: dict[str, Any] = {key: [] for key in list_keys}
    content["total"] = 0
    content["page_no"] = page_no
    content["page_size"] = page_size
    if extra:
        content.update(_json_deep_copy(extra))
    return content


def _empty_page_request_content(
    page_num: int,
    page_size: int,
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    content = {
        "pageNum": page_num,
        "pageSize": page_size,
        "totalSize": 0,
        "totalPages": 0,
        "content": [],
        "records": [],
        "rows": [],
        "list": [],
        "total": 0,
    }
    if extra:
        content.update(_json_deep_copy(extra))
    return content


def _looks_like_asset_path(requested_path: str) -> bool:
    normalized = requested_path.strip("/")
    if not normalized:
        return False
    path = Path(normalized)
    if path.suffix:
        return True
    return path.name in ASSET_FALLBACK_FILENAMES


def _asset_path_variants(asset_path: str) -> list[str]:
    normalized = asset_path.strip("/")
    if not normalized:
        return [""]

    variants: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        if candidate in seen:
            return
        seen.add(candidate)
        variants.append(candidate)

    add(normalized)
    encoded = "/".join(quote(unquote(part), safe=ASSET_PATH_SAFE_CHARS) for part in normalized.split("/"))
    add(encoded)
    return variants


def _is_placeholder_subject_name(name: Any, subject_id: int | None = None) -> bool:
    normalized = str(name or "").strip()
    if not normalized:
        return True
    if subject_id is not None and normalized == f"Subject {subject_id}":
        return True
    return bool(re.fullmatch(r"Subject\s+\d+", normalized))


def _non_placeholder_subject_name(name: Any, subject_id: int | None = None) -> str | None:
    normalized = str(name or "").strip()
    if _is_placeholder_subject_name(normalized, subject_id):
        return None
    return normalized


def _is_benign_placeholder_route(requested_path: str) -> bool:
    return requested_path.strip("/") in BENIGN_PLACEHOLDER_ROUTES


def _benign_placeholder_response() -> Response:
    return Response(
        content=b"<!doctype html><html><head><meta charset='utf-8'></head><body></body></html>",
        media_type="text/html",
    )


def _local_asset_candidates(store: MirrorStore, host: str, asset_path: str) -> list[Path]:
    candidates: list[Path] = []
    seen: set[Path] = set()

    def add(candidate: Path) -> None:
        if candidate in seen:
            return
        seen.add(candidate)
        candidates.append(candidate)

    for path_variant in _asset_path_variants(asset_path):
        asset_url = _build_live_url(host, f"/{path_variant}", "")
        indexed_asset = store.lookup_asset(asset_url)
        if indexed_asset is not None:
            add(store.root / indexed_asset["local_path"])

    def add_alias(alias_host: str, alias_path: str) -> None:
        for alias_variant in _asset_path_variants(alias_path):
            alias_url = _build_live_url(alias_host, f"/{alias_variant}", "")
            indexed_alias = store.lookup_asset(alias_url)
            if indexed_alias is not None:
                add(store.root / indexed_alias["local_path"])
            if is_same_origin_host(alias_host):
                add(store.root / "origin" / "steam.fun" / alias_variant)
            else:
                add(store.root / "external" / alias_host / alias_variant)
                add(store.root / "origin" / alias_host / alias_variant)

    def add_first_data_match(search_root: Path, filename: str) -> bool:
        if not search_root.is_dir():
            return False
        for candidate in search_root.rglob(filename):
            if candidate.is_file() and candidate.parent.name == "data":
                add(candidate)
                return True
        return False

    def add_course_data_fallbacks(asset_root: Path, relative_path: str) -> None:
        normalized_relative = relative_path.strip("/")
        if host != "wugecdn.steam.fun" or not normalized_relative.startswith("courses/"):
            return

        parts = Path(normalized_relative).parts
        if len(parts) < 4 or parts[-2] != "data":
            return

        sibling_root = asset_root.joinpath(*parts[:-3])
        lesson_dir_name = parts[-3]
        data_suffix = Path(*parts[-2:])
        filename = parts[-1]
        if filename.lower() not in COURSE_SHARED_DATA_FALLBACK_FILENAMES:
            return
        matched = False

        if sibling_root.is_dir():
            for sibling in sibling_root.iterdir():
                if not sibling.is_dir() or sibling.name == lesson_dir_name:
                    continue
                candidate = sibling / data_suffix
                if candidate.is_file():
                    add(candidate)
                    matched = True

        if matched:
            return

        family_root = asset_root / "courses" / parts[1]
        if len(parts) > 2:
            family_root = family_root / parts[2]

        if add_first_data_match(family_root, filename):
            return

        subject_root = asset_root / "courses" / parts[1]
        if add_first_data_match(subject_root, filename):
            return

        add_first_data_match(asset_root / "courses", filename)

    def add_course_index_neighbor_data_fallback(asset_root: Path, relative_path: str) -> None:
        normalized_relative = relative_path.strip("/")
        if host != "wugecdn.steam.fun" or not normalized_relative.startswith("courses/"):
            return

        parts = Path(normalized_relative).parts
        if len(parts) < 4 or parts[-2] != "data":
            return
        filename = parts[-1]
        if filename.lower() not in COURSE_SHARED_DATA_FALLBACK_FILENAMES:
            return

        lesson_dir = asset_root.joinpath(*parts[:-2])
        if not lesson_dir.is_dir():
            return

        for child in lesson_dir.iterdir():
            if not child.is_dir() or child.name == "data":
                continue
            candidate = child / "data" / filename
            if candidate.is_file():
                add(candidate)
                return

    def add_course_thumbnail_poster_fallback(asset_root: Path, relative_path: str) -> None:
        normalized_relative = relative_path.strip("/")
        if host != "wugecdn.steam.fun" or not normalized_relative.startswith("courses/"):
            return

        parts = Path(normalized_relative).parts
        if len(parts) < 5 or parts[-2] != "data":
            return

        filename = parts[-1]
        if not COURSE_DATA_THUMBNAIL_PATTERN.fullmatch(filename):
            return

        poster_root = asset_root.joinpath(*parts[:-4], "poster")
        if not poster_root.is_dir():
            return

        lesson_dir_name = parts[-3]
        decoded_lesson_dir_name = unquote(lesson_dir_name)
        prefixes: list[str] = []
        seen_prefixes: set[str] = set()

        def add_prefix(prefix: str) -> None:
            normalized_prefix = prefix.strip()
            if not normalized_prefix or normalized_prefix in seen_prefixes:
                return
            seen_prefixes.add(normalized_prefix)
            prefixes.append(normalized_prefix)

        add_prefix(lesson_dir_name)
        add_prefix(decoded_lesson_dir_name)

        lesson_number = re.match(r"^\d+", decoded_lesson_dir_name or lesson_dir_name)
        if lesson_number:
            add_prefix(lesson_number.group(0))

        for prefix in prefixes:
            for candidate in sorted(poster_root.glob(f"{prefix}*")):
                if candidate.is_file() and candidate.suffix.lower() in COURSE_POSTER_IMAGE_SUFFIXES:
                    add(candidate)
                    return

    def add_hashed_frontend_asset_fallback(asset_root: Path, relative_path: str) -> None:
        normalized_relative = relative_path.strip("/")
        asset_parts = Path(normalized_relative)
        filename_match = HASHED_FRONTEND_ASSET_PATTERN.fullmatch(asset_parts.name)
        if filename_match is None:
            return

        candidate_dir = asset_root.joinpath(*asset_parts.parts[:-1])
        if not candidate_dir.is_dir():
            return

        logical_prefix = filename_match.group("prefix")
        suffix = filename_match.group("suffix")
        unhashed_candidate = candidate_dir / f"{logical_prefix}{suffix}"
        if unhashed_candidate.is_file():
            add(unhashed_candidate)

        for candidate in sorted(candidate_dir.iterdir()):
            if not candidate.is_file() or candidate.name == asset_parts.name:
                continue
            if candidate.name == f"{logical_prefix}{suffix}":
                add(candidate)
                continue

            candidate_match = HASHED_FRONTEND_ASSET_PATTERN.fullmatch(candidate.name)
            if candidate_match is None:
                continue
            if candidate_match.group("prefix") == logical_prefix and candidate_match.group("suffix") == suffix:
                add(candidate)

    normalized_asset_path = asset_path.strip("/")
    if host == "wugecdn.steam.fun" and normalized_asset_path.startswith("courses/"):
        normalized_parts = Path(normalized_asset_path).parts
        filename = normalized_parts[-1] if normalized_parts else ""
        if filename.startswith("thbn") and len(filename) > 4:
            poster_relative = "/".join((*normalized_parts[:-1], "poster", filename[4:]))
            add_alias(host, poster_relative)
    if host == "jrcodework.oss-cn-zhangjiakou.aliyuncs.com" and SUMMER_WATERMELON_WORK_DIR in normalized_asset_path:
        add_alias(
            host,
            normalized_asset_path.replace(SUMMER_WATERMELON_WORK_DIR, SUMMER_WATERMELON_LOCAL_WORK_DIR),
        )
    if is_same_origin_host(host):
        svg_alias = MISSING_SVG_LIBRARY_ALIASES.get(normalized_asset_path)
        if svg_alias:
            add_alias("steam.fun", svg_alias)
        if normalized_asset_path.startswith("jrcode/assets/"):
            path_parts = Path(normalized_asset_path)
            stem = path_parts.stem
            if stem.endswith("Off"):
                off_to_on_alias = str(
                    path_parts.with_name(f"{stem[:-3]}On{path_parts.suffix}")
                ).replace("\\", "/")
                if off_to_on_alias != normalized_asset_path:
                    add_alias("steam.fun", off_to_on_alias)
    if not normalized_asset_path and not is_same_origin_host(host):
        for landing_path in EXTERNAL_ROOT_LANDING_PATHS:
            add_alias(host, landing_path)

    for path_variant in _asset_path_variants(asset_path):
        if is_same_origin_host(host):
            add(store.root / "origin" / "steam.fun" / path_variant)
            add_hashed_frontend_asset_fallback(store.root / "origin" / "steam.fun", path_variant)
            normalized = path_variant.lstrip("/")
            if normalized.startswith("img/"):
                filename = normalized.rsplit("/", 1)[-1]
                for filename_variant in _asset_path_variants(filename):
                    # Some teach-page tool icons are requested as same-origin /img/*
                    # even though the captured files live under the teachppt CDN path.
                    add(
                        store.root
                        / "external"
                        / "wugecdn.steam.fun"
                        / "resources"
                        / "static"
                        / "teachppt"
                        / filename_variant
                    )
                    # Older captures may store the same external host under origin/<host>/...
                    add(
                        store.root
                        / "origin"
                        / "wugecdn.steam.fun"
                        / "resources"
                        / "static"
                        / "teachppt"
                        / filename_variant
                    )
        else:
            add(store.root / "external" / host / path_variant)
            # Older captures stored non-steam.fun assets under origin/<host>/...
            add(store.root / "origin" / host / path_variant)
            add_hashed_frontend_asset_fallback(store.root / "external" / host, path_variant)
            add_hashed_frontend_asset_fallback(store.root / "origin" / host, path_variant)
            add_course_index_neighbor_data_fallback(store.root / "external" / host, path_variant)
            add_course_index_neighbor_data_fallback(store.root / "origin" / host, path_variant)
            add_course_data_fallbacks(store.root / "external" / host, path_variant)
            add_course_data_fallbacks(store.root / "origin" / host, path_variant)
            add_course_thumbnail_poster_fallback(store.root / "external" / host, path_variant)
            add_course_thumbnail_poster_fallback(store.root / "origin" / host, path_variant)
    return candidates


def _html_attribute_value(tag: str, attribute_name: str) -> str | None:
    quoted_match = re.search(
        rf"""\b{re.escape(attribute_name)}\s*=\s*(['"])(.*?)\1""",
        tag,
        re.IGNORECASE | re.DOTALL,
    )
    if quoted_match is not None:
        return quoted_match.group(2)
    bare_match = re.search(
        rf"""\b{re.escape(attribute_name)}\s*=\s*([^\s"'=<>`]+)""",
        tag,
        re.IGNORECASE,
    )
    if bare_match is not None:
        return bare_match.group(1)
    return None


def _prune_missing_frontend_asset_hints(store: MirrorStore, text: str) -> str:
    hint_rel_tokens = {"prefetch", "preload", "modulepreload"}

    # Pre-build a set of every steam.fun path known to the store so we can answer
    # asset-existence questions in O(1) instead of issuing per-link DB and disk
    # queries (which previously made SPA shell responses take 25+ seconds).
    known_steamfun_paths: set[str] = set()
    try:
        for url in store.all_asset_urls():
            if not url or not url.startswith(("https://steam.fun/", "http://steam.fun/")):
                continue
            parsed_url = urlparse(url)
            path = parsed_url.path.lstrip("/")
            if path:
                known_steamfun_paths.add(path)
                try:
                    known_steamfun_paths.add(unquote(path))
                except Exception:
                    pass
    except Exception:
        known_steamfun_paths = set()

    def is_synthetic(asset_path: str) -> bool:
        if not asset_path:
            return False
        normalized = asset_path.strip("/")
        if not normalized:
            return False
        asset_parts = Path(normalized)
        if (
            normalized.startswith(SVG_LIBRARY_PLACEHOLDER_PREFIX)
            and normalized.endswith(".svg")
        ):
            return True
        if normalized.endswith(".png") and any(
            normalized.startswith(prefix) for prefix in TRANSPARENT_PNG_PLACEHOLDER_PREFIXES
        ):
            return True
        if (
            asset_parts.parent.name == "data"
            and COURSE_DATA_THUMBNAIL_PATTERN.fullmatch(asset_parts.name)
        ):
            return True
        return False

    def has_local_asset(asset_path: str) -> bool:
        normalized = asset_path.strip("/")
        if not normalized:
            return False
        if normalized in known_steamfun_paths:
            return True
        for variant in _asset_path_variants(normalized):
            normalized_variant = variant.strip("/")
            if normalized_variant and normalized_variant in known_steamfun_paths:
                return True
            if normalized_variant and (store.root / "origin" / "steam.fun" / normalized_variant).is_file():
                return True
        return is_synthetic(normalized)

    def replace_link(match: re.Match[str]) -> str:
        tag = match.group(0)
        rel_value = _html_attribute_value(tag, "rel")
        if rel_value is None:
            return tag
        rel_tokens = {token.strip().lower() for token in rel_value.split() if token.strip()}
        if not rel_tokens.intersection(hint_rel_tokens):
            return tag
        if "stylesheet" in rel_tokens:
            return tag
        if "prefetch" in rel_tokens:
            return ""

        href_value = _html_attribute_value(tag, "href")
        if not href_value:
            return tag

        parsed_href = urlparse(href_value)
        if parsed_href.scheme and parsed_href.scheme not in {"http", "https"}:
            return tag
        if parsed_href.netloc and not is_same_origin_host(parsed_href.netloc):
            return tag

        asset_path = parsed_href.path or href_value
        if not _looks_like_asset_path(asset_path):
            return tag
        if has_local_asset(asset_path):
            return tag
        return ""

    return LINK_TAG_RE.sub(replace_link, text)


def _synthetic_asset_response(host: str, asset_path: str) -> Response | None:
    normalized_asset_path = asset_path.strip("/")
    asset_parts = Path(normalized_asset_path)
    if (
        host == "wugecdn.steam.fun"
        and asset_parts.parent.name == "data"
        and COURSE_DATA_THUMBNAIL_PATTERN.fullmatch(asset_parts.name)
    ):
        return Response(content=TRANSPARENT_PNG_BYTES, media_type="image/png")
    if not is_same_origin_host(host):
        return None
    if normalized_asset_path.endswith(".png") and any(
        normalized_asset_path.startswith(prefix) for prefix in TRANSPARENT_PNG_PLACEHOLDER_PREFIXES
    ):
        return Response(content=TRANSPARENT_PNG_BYTES, media_type="image/png")
    if not normalized_asset_path.startswith(SVG_LIBRARY_PLACEHOLDER_PREFIX) or not normalized_asset_path.endswith(".svg"):
        return None

    label = re.sub(r"[^A-Za-z0-9._-]+", " ", Path(normalized_asset_path).stem).strip() or "Asset"
    body = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160">'
        '<rect width="160" height="160" rx="24" fill="#f6f8fb"/>'
        '<rect x="16" y="16" width="128" height="128" rx="18" fill="#dfe8f3" stroke="#97abc3" stroke-width="3"/>'
        '<circle cx="80" cy="64" r="22" fill="#ffffff" stroke="#97abc3" stroke-width="3"/>'
        '<path d="M45 122c11-18 24-27 35-27s24 9 35 27" fill="none" stroke="#97abc3" stroke-width="6" '
        'stroke-linecap="round"/>'
        f'<text x="80" y="146" text-anchor="middle" font-size="11" font-family="Arial, sans-serif" fill="#4a6078">{label}</text>'
        "</svg>"
    ).encode("utf-8")
    return Response(content=body, media_type="image/svg+xml")


# Asset type extension -> content type mapping used by the missing-asset fallback.
# Keys are lowercase suffixes (including the leading dot).
_MISSING_ASSET_CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".eot": "application/vnd.ms-fontobject",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".txt": "text/plain; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
}


def _synthetic_missing_asset_response(host: str, asset_path: str) -> Response | None:
    """Return a minimal but well-formed 200 response for asset types we know how
    to stub out, so that missing wugecdn/steam.fun course resources stop
    showing as 404s in the browser. Only invoked for trusted hosts."""
    if not (is_same_origin_host(host) or host == "wugecdn.steam.fun"):
        return None
    normalized = asset_path.strip("/")
    if not normalized:
        return None
    suffix = Path(normalized).suffix.lower()
    media_type = _MISSING_ASSET_CONTENT_TYPES.get(suffix)
    if media_type is None:
        return None
    if suffix in {".css", ".js", ".mjs"}:
        return None
    if media_type.startswith("image/") and not media_type.endswith("svg+xml"):
        # PNG bytes only decode as PNG. For other image/* types (jpeg, gif,
        # webp, bmp) serve a tiny transparent GIF so the browser still shows
        # a 200 with a decodable body.
        body = TRANSPARENT_PNG_BYTES if media_type == "image/png" else TRANSPARENT_GIF_BYTES
        return Response(content=body, media_type=media_type)
    if media_type.startswith("font/"):
        return None
    if media_type == "image/svg+xml":
        body = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1" '
            'viewBox="0 0 1 1"></svg>'
        ).encode("utf-8")
        return Response(content=body, media_type=media_type)
    if media_type == "application/json":
        return Response(content=b"{}", media_type=media_type)
    return Response(content=b"", media_type=media_type)


def _build_live_url(host: str, path: str, query: str) -> str:
    if is_same_origin_host(host):
        live_url = f"{BASE_URL}{path}"
    else:
        live_url = f"https://{host}{path}"
    if query:
        live_url = f"{live_url}?{query}"
    return live_url


def _with_query_updates(
    parsed_url: Any,
    *,
    path: str | None = None,
    defaults: dict[str, str] | None = None,
    updates: dict[str, str] | None = None,
) -> str:
    query = dict(parse_qsl(parsed_url.query, keep_blank_values=True))
    if defaults:
        for key, value in defaults.items():
            query.setdefault(key, value)
    if updates:
        query.update(updates)
    normalized_query = urlencode(sorted(query.items()))
    return urlunparse(parsed_url._replace(path=path or parsed_url.path, query=normalized_query))


def _api_lookup_url_variants(url: str) -> list[str]:
    parsed = urlparse(url)
    variants: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        if candidate in seen:
            return
        seen.add(candidate)
        variants.append(candidate)

    add(url)
    add(_with_query_updates(parsed))

    if parsed.path in {"/api/prepare/get/curriculumMaterialList", "/api/prepare/get/currculumMaterialList"}:
        path_variants = [
            "/api/prepare/get/curriculumMaterialList",
            "/api/prepare/get/currculumMaterialList",
        ]
        for candidate_path in path_variants:
            add(
                _with_query_updates(
                    parsed,
                    path=candidate_path,
                    defaults={"page_no": "1", "page_size": "200"},
                )
            )

    if parsed.path == "/api/get/campus/curriculum/list/by/page":
        for page_size in ("20", "100"):
            add(_with_query_updates(parsed, updates={"page_size": page_size}))

    return variants


SCRIPT_TAG_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
MESSAGE_BOX_WRAPPER_RE = re.compile(
    r'<div\b[^>]*class="[^"]*\bel-message-box__wrapper\b[^"]*"[^>]*>.*?</div>',
    re.IGNORECASE | re.DOTALL,
)
MODAL_BACKDROP_RE = re.compile(
    r'<div\b[^>]*class="[^"]*\bv-modal\b[^"]*"[^>]*></div>',
    re.IGNORECASE | re.DOTALL,
)
LOGO_IMAGE_ERROR_RE = re.compile(
    r'<div\b[^>]*class="[^"]*\bel-image\s+logo_img\b[^"]*"[^>]*>\s*'
    r'<div\b[^>]*class="[^"]*\bel-image__error\b[^"]*"[^>]*>.*?</div>\s*<!---->\s*</div>',
    re.IGNORECASE | re.DOTALL,
)


def _preferred_profile_for_route(route_key: str) -> str | None:
    normalized = _normalize_route_path(route_key)
    if _is_teacher_classroom_route(normalized):
        return "teacher"
    if _is_teacher_competition_route(normalized):
        return "teacher"
    if normalized.startswith("/code-classroom"):
        return "student"
    if normalized.startswith("/school-home-page"):
        return "teacher"
    if normalized.startswith("/background"):
        return "admin"
    return None


def _route_aliases(route_key: str) -> list[str]:
    aliases = [route_key]
    if route_key == "/code-classroom/classroom-index":
        aliases.append("/code-classroom")
    if route_key == "/school-home-page":
        aliases.append("/")
    return aliases


def _is_login_redirect_capture(final_url: str) -> bool:
    parsed = urlparse(final_url)
    path = parsed.path.rstrip("/") or "/"
    return path in {"/login", "/background/login"}


def _is_login_route(path: str) -> bool:
    normalized = _normalize_route_path(path)
    return normalized in {"/login", "/background/login"}


def _allows_implicit_profile_bootstrap(route_key: str) -> bool:
    normalized = _normalize_route_path(route_key)
    if _is_login_route(normalized):
        return False
    if _is_teacher_classroom_route(normalized):
        return True
    if normalized.startswith("/school-home-page"):
        return True
    if normalized.startswith("/background"):
        return True
    if normalized.startswith("/code-classroom"):
        return True
    if _is_teacher_competition_route(normalized):
        return True
    return False


def _preferred_profile_for_request(store: MirrorStore, request: Request, route_key: str) -> str | None:
    profile = _resolve_profile(store, request)
    if profile:
        return profile["profile_name"]
    profile_name = _resolve_profile_name(store, request)
    if profile_name:
        return profile_name
    if not _allows_implicit_profile_bootstrap(route_key):
        return None
    return _preferred_profile_for_route(route_key)


def _infer_profile_from_request(request: Request) -> str | None:
    explicit_profile = request.headers.get("x-mirror-profile")
    if explicit_profile:
        return explicit_profile

    cookie_profile = (request.cookies.get("mirror_profile") or "").strip()
    if cookie_profile:
        return cookie_profile

    referer = request.headers.get("referer") or ""
    referer_path = urlparse(referer).path
    if _is_teacher_classroom_route(referer_path):
        return "teacher"
    if _is_teacher_competition_route(referer_path):
        return "teacher"
    if referer_path.startswith("/background/course-management"):
        return "teacher"
    if referer_path.startswith("/background"):
        return "admin"
    if referer_path.startswith("/school-home-page"):
        return "teacher"
    if referer_path.startswith("/code-classroom"):
        return "student"
    if referer_path.startswith("/exam-stu"):
        return "student"

    request_path = request.url.path
    if request_path.startswith("/api/stuexam/"):
        return "student"
    if request_path.startswith(STUDENT_API_PREFIXES):
        return "student"
    if request_path.startswith(TEACHER_API_PREFIXES):
        return "teacher"
    return None


def _profile_role(profile_name: str | None, profile: dict[str, Any] | None = None) -> str | None:
    return resolve_profile_role(profile_name, profile)


def _default_frontend_route_for_role(profile_role: str | None) -> str | None:
    return default_route_for_role(profile_role)


def _is_teacher_like_role(profile_role: str | None) -> bool:
    return profile_role in {"teacher", "admin"}


def _allowed_frontend_roles(route_key: str) -> frozenset[str] | None:
    return roles_for_frontend_route(_normalize_route_path(route_key))


def _protected_frontend_redirect_target(
    store: MirrorStore,
    request: Request,
    route_key: str,
) -> str | None:
    allowed_roles = _allowed_frontend_roles(route_key)
    if allowed_roles is None:
        return None

    profile = _resolve_authenticated_profile(store, request)
    profile_role = _profile_role(profile.get("profile_name"), profile) if profile else None
    if profile_role is None:
        local_target = request.url.path
        if request.url.query:
            local_target = f"{local_target}?{request.url.query}"
        return f"/login?next={quote(local_target, safe='')}"
    if profile_role not in allowed_roles:
        return _default_frontend_route_for_role(profile_role) or "/login"
    return None


def _required_api_roles(path: str) -> frozenset[str] | None:
    if path.startswith("/java-api/student/") or path.startswith("/api/stu/"):
        return frozenset({"student"})
    if path.startswith("/java-api/school/") or path.startswith("/java-api/auth/"):
        return frozenset({"teacher", "admin"})
    return None


def _api_authorization_error(store: MirrorStore, request: Request) -> JSONResponse | None:
    allowed_roles = _required_api_roles(request.url.path)
    if allowed_roles is None or request.method == "OPTIONS":
        return None

    profile = _resolve_authenticated_profile(store, request)
    if profile is None:
        return JSONResponse(
            {"success": False, "error": {"code": "AuthRequired", "message": "请先登录"}},
            status_code=401,
        )
    profile_role = _profile_role(profile.get("profile_name"), profile)
    if profile_role not in allowed_roles:
        return JSONResponse(
            {"success": False, "error": {"code": "Forbidden", "message": "无权访问该功能"}},
            status_code=403,
        )
    return None


def _workspace_role_error(
    store: MirrorStore,
    request: Request,
    allowed_roles: frozenset[str],
) -> JSONResponse | None:
    profile = _resolve_authenticated_profile(store, request)
    if profile is None:
        return JSONResponse(
            {"success": False, "error": {"code": "AuthRequired", "message": "请先登录"}},
            status_code=401,
        )
    role = _profile_role(profile.get("profile_name"), profile)
    if role not in allowed_roles:
        return JSONResponse(
            {"success": False, "error": {"code": "Forbidden", "message": "无权执行该操作"}},
            status_code=403,
        )
    return None


def _profile_is_disabled(profile: dict[str, Any] | None) -> bool:
    if not isinstance(profile, dict):
        return False
    fresh_auth = profile.get("fresh_auth") if isinstance(profile.get("fresh_auth"), dict) else {}
    user_info = fresh_auth.get("userInfo") if isinstance(fresh_auth.get("userInfo"), dict) else {}
    if "tchState" in user_info and not bool(user_info.get("tchState")):
        return True
    normalized_state = str(user_info.get("state") or "").strip().lower()
    return normalized_state in {"停用", "离职", "disabled", "inactive", "0"}


def _profile_specific_route_aliases(route_key: str, preferred_profile: str | None) -> list[str]:
    if route_key == "/code-classroom/classroom-index" and preferred_profile == "teacher":
        aliases = ["/code-classroom", route_key]
    else:
        aliases = [route_key]
    if route_key.startswith("/school-home-page/"):
        aliases.extend(["/school-home-page", "/"])
    if preferred_profile == "teacher":
        if _is_teacher_classroom_route(route_key):
            aliases.extend(["/code-classroom", "/code-classroom/classroom-index"])
    if preferred_profile == "admin" and route_key.startswith("/background/"):
        aliases.append("/background")
    if route_key == "/code-classroom/classroom-index":
        if preferred_profile == "student":
            aliases.extend(["/code-classroom/classroom-index", "/code-classroom"])
        else:
            aliases.append("/code-classroom")
    if route_key == "/school-home-page":
        aliases.append("/")
    deduped: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        if alias in seen:
            continue
        seen.add(alias)
        deduped.append(alias)
    return deduped


def _lookup_login_route_capture(
    store: MirrorStore,
    login_route: str,
    *,
    preferred_profile: str | None = None,
) -> dict[str, Any] | None:
    normalized_login_route = _normalize_route_path(login_route)
    preferred_rank = {
        "admin": "WHEN 'admin' THEN 0 WHEN 'teacher' THEN 1 WHEN 'student' THEN 2 ELSE 3",
        "teacher": "WHEN 'teacher' THEN 0 WHEN 'student' THEN 1 ELSE 2",
        "student": "WHEN 'student' THEN 0 WHEN 'teacher' THEN 1 ELSE 2",
    }.get(preferred_profile, "WHEN 'teacher' THEN 0 WHEN 'student' THEN 1 ELSE 2")
    with store._connect() as connection:
        rows = connection.execute(
            f"""
            SELECT profile_name, route, final_url, status, html_path, captured_xhr_count
            FROM routes
            ORDER BY CASE profile_name
                {preferred_rank}
            END, LENGTH(route), captured_xhr_count DESC
            """
        ).fetchall()

    for row in rows:
        final_url = str(row["final_url"] or "")
        if not _is_login_redirect_capture(final_url):
            continue
        parsed = urlparse(final_url)
        final_path = parsed.path.rstrip("/") or "/"
        if final_path != normalized_login_route:
            continue
        return {
            "profile_name": row["profile_name"],
            "route": row["route"],
            "final_url": row["final_url"],
            "status": row["status"],
            "html_path": row["html_path"],
            "captured_xhr_count": row["captured_xhr_count"],
        }
    return None


def _fetch_static_asset(live_url: str) -> requests.Response | None:
    parsed = urlparse(live_url)
    candidate_urls = [live_url]
    if not is_same_origin_host(parsed.netloc) and parsed.scheme == "https":
        candidate_urls.append(parsed._replace(scheme="http").geturl())

    for candidate_url in candidate_urls:
        candidate_parsed = urlparse(candidate_url)
        candidate_origin = BASE_URL if is_same_origin_host(candidate_parsed.netloc) else f"{candidate_parsed.scheme}://{candidate_parsed.netloc}"
        candidate_referer = f"{candidate_origin}/"
        candidate_path = unquote(candidate_parsed.path or "")
        if is_same_origin_host(candidate_parsed.netloc):
            candidate_referer = f"{BASE_URL}/"
        elif candidate_parsed.netloc == "wugecdn.steam.fun" and candidate_path.startswith("/courses/") and "/data/" in candidate_path:
            lesson_root, _ = candidate_parsed.path.rsplit("/data/", 1)
            candidate_referer = urlunparse(
                candidate_parsed._replace(path=f"{lesson_root}/index.html", query="", fragment="")
            )
        headers = {
            **STATIC_FETCH_HEADERS,
            "Referer": candidate_referer,
            "Origin": candidate_origin,
        }
        try:
            response = requests.get(candidate_url, headers=headers, timeout=60, stream=True)
        except requests.RequestException:
            continue
        if response.status_code < 400:
            return response
        response.close()
    return None


def _first_query_value(request: Request, key: str) -> str | None:
    values = request.query_params.getlist(key)
    if not values:
        return None
    value = values[0].strip()
    return value or None


def _normalize_route_path(path: str) -> str:
    if not path:
        return "/"
    normalized = path.rstrip("/")
    return normalized or "/"


def _is_core_background_route(path: str | None) -> bool:
    normalized = _normalize_route_path(path or "")
    return normalized.startswith(CORE_BACKGROUND_ROUTE_PREFIX)


def _is_core_background_request(request: Request, route_key: str | None = None) -> bool:
    if route_key and _is_core_background_route(route_key):
        return True
    if _is_core_background_route(request.url.path):
        return True
    referer = request.headers.get("referer") or ""
    referer_path = urlparse(referer).path if referer else ""
    return _is_core_background_route(referer_path)


def _is_teacher_classroom_route(path: str) -> bool:
    normalized = _normalize_route_path(path)
    if normalized in TEACHER_CLASSROOM_ROOT_ROUTES:
        return True
    return normalized.startswith("/code-classroom/prepare-lessons/") or normalized.startswith("/code-classroom/teach-lessons/")


def _is_teacher_competition_route(path: str) -> bool:
    normalized = _normalize_route_path(path)
    return normalized.startswith(TEACHER_COMPETITION_ROUTE_PREFIXES)


def _should_bootstrap_teacher_context(path: str) -> bool:
    normalized = _normalize_route_path(path)
    if normalized in TEACHER_SESSION_ROOT_ROUTES:
        return True
    if _is_teacher_competition_route(normalized):
        return True
    return normalized.startswith("/code-classroom/prepare-lessons/") or normalized.startswith("/code-classroom/teach-lessons/")


def _extract_curr_mat_id_from_request(request: Request) -> int | None:
    raw = _first_query_value(request, "curriculumMaterial_id")
    if raw is None:
        return None
    if raw.isdigit():
        return int(raw)
    return None


def _extract_teaching_plan_id_from_request(request: Request) -> int | None:
    for key in ("teaching_plan_id", "tchPlanId", "teachingPlanId"):
        raw = _first_query_value(request, key)
        if raw and raw.isdigit():
            return int(raw)
    return None


def _extract_class_id_from_request(request: Request, payload: Any | None = None) -> int | None:
    raw = _request_payload_value(
        request,
        payload,
        "id",
        "classId",
        "classes_id",
        "curriculum_class_id",
        "curriculumClassId",
        "class_id",
    )
    return _parse_int_like(raw)


def _extract_class_id_from_referer(request: Request) -> int | None:
    referer = str(request.headers.get("referer") or "").strip()
    if not referer:
        return None
    try:
        parsed = urlparse(referer)
    except Exception:
        return None
    if _normalize_route_path(parsed.path) != "/school-home-page/class-management1/divide-class1":
        return None
    referer_id_values = parse_qs(parsed.query, keep_blank_values=True).get("id") or []
    if not referer_id_values:
        return None
    return _parse_int_like(referer_id_values[0])


def _resolve_class_context_id(request: Request, payload: Any | None = None) -> int | None:
    explicit_class_id = _extract_class_id_from_request(request, payload)
    if explicit_class_id is not None:
        return explicit_class_id
    return _extract_class_id_from_referer(request)


def _extract_request_int_set(request: Request, payload: Any | None = None, *keys: str) -> set[int]:
    values: list[int] = []
    for key in keys:
        raw = _request_payload_value(request, payload, key)
        if raw not in (None, ""):
            _append_int_values(values, raw)
    return set(values)


def _resolve_student_end_date(
    request: Request,
    payload: Any,
    store: MirrorStore | None = None,
    *,
    student_id: int | None = None,
) -> str:
    type_value = _parse_int_like(payload.get("type")) if isinstance(payload, dict) else None
    if type_value == 1:
        day_num = _parse_int_like(payload.get("dayNum")) if isinstance(payload, dict) else None
        if day_num is None or day_num <= 0:
            return ""

        # The duration dialog previews from a student's remaining validity
        # when it is still active. Match that behavior for every selected
        # student, falling back to today for expired or unset validity.
        baseline_date = datetime.now()
        if store is not None and student_id is not None:
            overlay = store.get_student_overlay(student_id) or {}
            current_end_date = str(overlay.get("end_date") or "").strip()[:10]
            if current_end_date:
                try:
                    parsed_end_date = datetime.strptime(current_end_date, "%Y-%m-%d")
                except ValueError:
                    parsed_end_date = None
                if parsed_end_date is not None and parsed_end_date > baseline_date:
                    baseline_date = parsed_end_date
        return (baseline_date + timedelta(days=day_num)).strftime("%Y-%m-%d")

    direct_value = _request_payload_value(
        request,
        payload,
        "endDate",
        "end_date",
        "studyDate",
        "study_date",
        "validityDate",
        "validity_date",
        "expireDate",
        "expire_date",
    )
    direct_text = str(direct_value or "").strip()
    if direct_text:
        return direct_text[:10]
    return ""


def _student_member_class_ids(store: MirrorStore, student_id: int | str | None) -> set[int]:
    normalized_student_id = _coerce_int(student_id)
    if normalized_student_id is None:
        return set()

    class_ids: set[int] = set()
    candidate_class_ids: set[int] = set()
    for class_row in store.list_classes():
        if not isinstance(class_row, dict):
            continue
        class_id = _coerce_int(class_row.get("id"))
        if class_id is not None:
            candidate_class_ids.add(class_id)
    for plan in store.list_teaching_plans():
        if not isinstance(plan, dict):
            continue
        class_info = plan.get("classInfo") if isinstance(plan.get("classInfo"), dict) else {}
        class_id = _coerce_int(class_info.get("id") or plan.get("curriculum_class_id"))
        if class_id is not None:
            candidate_class_ids.add(class_id)

    for class_id in candidate_class_ids:
        payload = store.get_class_student_payload(class_id)
        if not isinstance(payload, dict):
            continue
        student_rows = payload.get("studentList") or []
        if not isinstance(student_rows, list):
            continue
        for row in student_rows:
            if not isinstance(row, dict):
                continue
            candidate_id = _coerce_int(row.get("student_user_id"))
            if candidate_id is None:
                student_info = row.get("studentInfo") if isinstance(row.get("studentInfo"), dict) else {}
                candidate_id = _coerce_int(student_info.get("id"))
            if candidate_id == normalized_student_id:
                class_ids.add(class_id)
                break
    return class_ids


def _material_asset_score(material: dict[str, Any]) -> int:
    score = 0
    for key in (
        "ppt_url",
        "video_url",
        "stu_note_url",
        "knowledge_point_url",
        "teach_template_url",
        "home_template_url",
        "other_meterial_url",
    ):
        if material.get(key):
            score += 1
    return score


def _default_teacher_curriculum_material(store: MirrorStore) -> dict[str, Any] | None:
    materials = store.list_curriculum_materials()
    if not materials:
        return None
    return max(
        materials,
        key=lambda material: (
            _material_asset_score(material),
            int(material.get("id") or 0),
        ),
    )


def _resolve_teacher_curriculum_material(store: MirrorStore, request: Request) -> dict[str, Any] | None:
    curr_mat_id = _extract_curr_mat_id_from_request(request)
    if curr_mat_id is not None:
        material = store.find_curriculum_material(curr_mat_id)
        if material is not None:
            return material
    return _default_teacher_curriculum_material(store)


def _material_subject_id(material: dict[str, Any] | None) -> int | None:
    if not isinstance(material, dict):
        return None
    for key in ("subject_id", "subjectId", "subject_code", "subjectCode"):
        normalized = _coerce_int(material.get(key))
        if normalized is not None:
            return normalized
    return None


def _material_asset_url(store: MirrorStore, material: dict[str, Any] | None, keys: tuple[str, ...]) -> str:
    if not isinstance(material, dict):
        return ""

    fallback = ""
    for key in keys:
        value = material.get(key)
        if value in (None, ""):
            continue
        text = str(value).strip()
        if not text:
            continue
        if not fallback:
            fallback = text
        if store.lookup_asset(text) is not None:
            return text
    return fallback


def _select_local_work_material(
    store: MirrorStore,
    request: Request,
    selected_plan: dict[str, Any] | None,
    requested_subject_code: Any = None,
) -> dict[str, Any] | None:
    materials = [material for material in store.list_curriculum_materials() if isinstance(material, dict)]
    if not materials:
        return None

    class_info = (selected_plan or {}).get("classInfo") if isinstance((selected_plan or {}).get("classInfo"), dict) else {}
    requested_subject_id = _coerce_int(requested_subject_code)
    requested_curr_mat_id = _extract_curr_mat_id_from_request(request)
    plan_material_id = _coerce_int(
        (selected_plan or {}).get("curriculum_meterial_id")
        or (selected_plan or {}).get("curriculum_material_id")
        or class_info.get("curriculum_meterial_id")
        or class_info.get("curriculum_material_id")
    )
    plan_curriculum_id = _coerce_int(
        (selected_plan or {}).get("curriculum_id")
        or class_info.get("curriculum_id")
    )
    plan_subject_id = _coerce_int(
        (selected_plan or {}).get("subject_id")
        or (selected_plan or {}).get("subject_code")
        or class_info.get("subject_id")
        or class_info.get("subject_code")
    )

    def score(material: dict[str, Any]) -> tuple[int, int]:
        material_id = _coerce_int(material.get("id")) or 0
        material_curriculum_id = _coerce_int(material.get("curriculum_id"))
        material_subject_id = _material_subject_id(material)
        score_value = _material_asset_score(material)
        if requested_curr_mat_id is not None and material_id == requested_curr_mat_id:
            score_value += 1000
        if plan_material_id is not None and material_id == plan_material_id:
            score_value += 750
        if plan_curriculum_id is not None and material_curriculum_id == plan_curriculum_id:
            score_value += 400
        if plan_subject_id is not None and material_subject_id == plan_subject_id:
            score_value += 200
        if requested_subject_id is not None and material_subject_id == requested_subject_id:
            score_value += 150
        if _material_asset_url(store, material, ("exampal_work_url", "teach_template_url", "home_template_url")):
            score_value += 30
        if _material_asset_url(store, material, ("other_meterial_url", "img_url", "ppt_url")):
            score_value += 10
        return score_value, material_id

    return max(materials, key=score)


def _fallback_local_work_students(store: MirrorStore, request: Request | None = None) -> list[dict[str, Any]]:
    students = [student for student in store.list_local_students() if isinstance(student, dict)]
    if students:
        return students
    student_context = _student_profile_context(store, request)
    student_id = _coerce_int(student_context.get("student_id")) or 1
    display_name = str(student_context.get("display_name") or "Mirror Student").strip()
    account_name = str(student_context.get("account_name") or f"mirror-student-{student_id}").strip()
    school_name = str(
        student_context.get("school_info", {}).get("name") or _teacher_primary_campus_name(store)
    ).strip()
    return [
        {
            "id": student_id,
            "campus_id": _coerce_int(student_context.get("campus_id")) or _teacher_primary_campus_id(store) or 0,
            "name": account_name,
            "realname": display_name,
            "sex": "M",
            "normal_state": "1",
            "phone_num": "",
            "school_name": school_name or _teacher_primary_campus_name(store),
            "grade": "",
            "leader": "",
            "remark": "local-fallback",
            "study_date": "",
            "headimg_url": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "created_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    ]


def _build_local_work_dataset(
    store: MirrorStore,
    request: Request,
    *,
    requested_subject_code: Any = None,
    title_filter: str = "",
    page_no: int | None = None,
    page_size: int | None = None,
) -> dict[str, Any]:
    if page_no is None or page_size is None:
        page_no, page_size, start = _page_window(request)
    else:
        page_no = max(page_no, 1)
        page_size = max(page_size, 1)
        start = (page_no - 1) * page_size

    selected_plan = _select_teaching_plan(store, request) or {}
    selected_material = _select_local_work_material(store, request, selected_plan, requested_subject_code)
    if selected_material is None:
        selected_material = _resolve_teacher_curriculum_material(store, request)

    resolved_subject_id = (
        _material_subject_id(selected_material)
        or _coerce_int(requested_subject_code)
        or _coerce_int(selected_plan.get("subject_id") or selected_plan.get("subject_code"))
        or 1
    )
    subject_snapshot = _teacher_subject_snapshot(store, str(resolved_subject_id))
    lesson_id = _coerce_int((selected_material or {}).get("id")) or _coerce_int(selected_plan.get("id")) or 0
    teaching_plan_id = _coerce_int(selected_plan.get("id")) or 0
    class_info = selected_plan.get("classInfo") if isinstance(selected_plan.get("classInfo"), dict) else {}
    school_info = _teacher_school_info(store)
    teacher_info = _teacher_user_info(store)
    edu_id = _coerce_int(selected_plan.get("educational_institution_id") or school_info.get("id")) or 0
    edu_campus_id = _coerce_int(
        selected_plan.get("educational_institution_campus_id")
        or class_info.get("educational_institution_campus_id")
        or school_info.get("eduCampusId")
        or school_info.get("educationalInstitutionCampusId")
        or _teacher_primary_campus_id(store)
    ) or 0
    campus_name = class_info.get("campusName") or _teacher_primary_campus_name(store)
    class_name = class_info.get("name") or selected_plan.get("className") or ""
    lesson_title = str(
        (selected_material or {}).get("title")
        or (selected_plan.get("lessionInfo") or {}).get("title")
        or selected_plan.get("title")
        or "鏈湴璇惧爞浣滃搧"
    )
    work_url = _material_asset_url(
        store,
        selected_material,
        (
            "exampal_work_url",
            "teach_template_url",
            "home_template_url",
            "ppt_url",
            "video_url",
            "knowledge_point_url",
            "stu_note_url",
            "other_meterial_url",
            "img_url",
        ),
    )
    cover_url = _material_asset_url(
        store,
        selected_material,
        (
            "other_meterial_url",
            "img_url",
            "ppt_url",
            "stu_note_url",
            "knowledge_point_url",
            "video_url",
            "teach_template_url",
            "home_template_url",
            "exampal_work_url",
        ),
    ) or work_url
    work_type = _coerce_int(subject_snapshot.get("subjectCode")) or resolved_subject_id
    language = {
        1: "jrcode",
        2: "scratch",
        3: "python",
        4: "cpp",
    }.get(work_type, "jrcode")
    created_time = (
        str(selected_plan.get("class_date") or selected_plan.get("start_class_date") or "").strip()
        or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    title_filter_normalized = title_filter.strip().lower()

    rows: list[dict[str, Any]] = []
    for index, student in enumerate(_fallback_local_work_students(store, request), start=1):
        student_id = _coerce_int(student.get("id")) or index
        overlay = store.get_student_overlay(student_id) or {}
        display_name = _student_display_name(student, default_id=student_id)
        account_name = str(student.get("name") or f"mirror-student-{student_id}")
        headimg_url = str(
            student.get("headimg_url")
            or "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png"
        )
        row_title = lesson_title
        row_id = teaching_plan_id * 1000 + student_id if teaching_plan_id else student_id
        student_info = _build_local_student_entry(student, store) if isinstance(student, dict) else {}
        openid = str(overlay.get("open_id") or "") if overlay.get("open_id") not in (None, "") else ""
        authorizer_openid = (
            str(overlay.get("authorizer_openid") or "")
            if overlay.get("authorizer_openid") not in (None, "")
            else ""
        )
        row = {
            "id": row_id,
            "workId": row_id,
            "title": row_title,
            "lessonTitle": row_title,
            "name": display_name,
            "username": account_name,
            "realName": display_name,
            "headImgUrl": headimg_url,
            "headimg_url": headimg_url,
            "covers": cover_url,
            "work_url": work_url,
            "workUrl": work_url,
            "work_type": work_type,
            "workType": str(work_type),
            "language": language,
            "subject_code": work_type,
            "subjectCode": str(work_type),
            "subject_name": subject_snapshot.get("subjectName") or "",
            "subjectName": subject_snapshot.get("subjectName") or "",
            "lesson_id": lesson_id,
            "lessonId": lesson_id,
            "teaching_plan_id": teaching_plan_id,
            "teachingPlanId": teaching_plan_id,
            "tchPlanId": teaching_plan_id,
            "stu_tch_plan_id": student_id,
            "stuTchPlanId": student_id,
            "stu_user_id": student_id,
            "stuUserId": student_id,
            "student_user_id": student_id,
            "educational_institution_id": edu_id,
            "eduId": edu_id,
            "educational_institution_campus_id": edu_campus_id,
            "eduCampusId": edu_campus_id,
            "className": class_name,
            "campusName": campus_name,
            "is_marking": False,
            "markpoint": 0,
            "remark": "",
            "is_good": index == 1,
            "is_only": True,
            "is_local": True,
            "openid": openid,
            "openId": openid,
            "authorizer_openid": authorizer_openid,
            "authorizerOpenid": authorizer_openid,
            "is_send_tch_comment_wx_message": False,
            "created_time": created_time,
            "updated_time": created_time,
            "submit_time": created_time,
            "studentInfo": student_info,
            "stuInfo": {
                "id": student_id,
                "name": display_name,
                "realName": display_name,
                "headimgUrl": headimg_url,
                "headimg_url": headimg_url,
            },
        }
        if not title_filter_normalized or title_filter_normalized in row_title.lower() or title_filter_normalized in display_name.lower():
            rows.append(row)

    page_rows = rows[start:start + page_size]
    lesson_info = {
        "id": lesson_id,
        "lessonId": lesson_id,
        "title": lesson_title,
        "lessonTitle": lesson_title,
        "subjectCode": subject_snapshot.get("subjectCode") or str(work_type),
        "subjectName": subject_snapshot.get("subjectName") or "",
        "teachingPlanId": teaching_plan_id,
        "tchPlanId": teaching_plan_id,
        "covers": cover_url,
        "workUrl": work_url,
        "imgUrl": (selected_material or {}).get("img_url") or cover_url,
        "curriculumMaterialId": _coerce_int((selected_material or {}).get("id")) or 0,
    }
    return {
        "rows": page_rows,
        "total": len(rows),
        "page_no": page_no,
        "page_size": page_size,
        "subject_snapshot": subject_snapshot,
        "lesson_id": lesson_id,
        "lesson_title": lesson_title,
        "lesson_info": lesson_info,
    }


def _student_profile_context(store: MirrorStore, request: Request | None = None) -> dict[str, Any]:
    student_profile = store.get_profile("student") or {}
    if request is not None:
        try:
            resolved = _resolve_profile(store, request)
        except Exception:
            resolved = None
        if isinstance(resolved, dict) and resolved.get("login_path") == STUDENT_LOGIN_PATH:
            student_profile = resolved
    fresh_auth = student_profile.get("fresh_auth") if isinstance(student_profile.get("fresh_auth"), dict) else {}
    user_info = fresh_auth.get("userInfo") if isinstance(fresh_auth.get("userInfo"), dict) else {}
    stu_user_info = user_info.get("stuUserInfo") if isinstance(user_info.get("stuUserInfo"), dict) else {}
    stu_base_info = (
        stu_user_info.get("stuUserInfo") if isinstance(stu_user_info.get("stuUserInfo"), dict) else {}
    )
    school_info = fresh_auth.get("schoolInfo") if isinstance(fresh_auth.get("schoolInfo"), dict) else {}

    def first_int(*values: Any) -> int | None:
        for value in values:
            normalized = _coerce_int(value)
            if normalized is not None:
                return normalized
        return None

    student_id = first_int(
        stu_user_info.get("id"),
        user_info.get("id"),
        stu_base_info.get("id"),
    )
    campus_id = first_int(
        stu_base_info.get("eduCampusId"),
        stu_user_info.get("eduCampusId"),
        user_info.get("eduCampusId"),
        school_info.get("eduCampusId"),
        school_info.get("educationalInstitutionCampusId"),
        _teacher_primary_campus_id(store),
    )
    school_id = first_int(
        school_info.get("id"),
        school_info.get("schoolId"),
        user_info.get("schoolId"),
        user_info.get("eduId"),
    )

    display_name = ""
    for candidate in (
        stu_base_info.get("realName"),
        stu_base_info.get("realname"),
        stu_user_info.get("realName"),
        stu_user_info.get("realname"),
        user_info.get("realName"),
        user_info.get("realname"),
    ):
        text = str(candidate or "").strip()
        if text:
            display_name = text
            break

    account_name = ""
    for candidate in (
        stu_user_info.get("name"),
        user_info.get("name"),
        user_info.get("username"),
        student_profile.get("username"),
    ):
        text = str(candidate or "").strip()
        if text:
            account_name = text
            break

    return {
        "profile": student_profile,
        "fresh_auth": fresh_auth,
        "user_info": user_info,
        "stu_user_info": stu_user_info,
        "stu_base_info": stu_base_info,
        "school_info": school_info,
        "student_id": student_id,
        "campus_id": campus_id,
        "school_id": school_id,
        "display_name": display_name,
        "account_name": account_name,
    }


def _student_subject_rows(store: MirrorStore) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for subject in _teacher_subject_catalog(store):
        if not isinstance(subject, dict):
            continue
        subject_id = _coerce_int(subject.get("id") or subject.get("subject_id") or subject.get("code"))
        if subject_id is None:
            continue
        row = _json_deep_copy(subject)
        subject_code = _coerce_int(row.get("code")) or subject_id
        subject_name = str(row.get("name") or row.get("subjectName") or row.get("subject_name") or "").strip()
        row["id"] = subject_id
        row["code"] = subject_code
        row["subject_id"] = subject_id
        row["subjectId"] = subject_id
        row["subject_code"] = subject_code
        row["subjectCode"] = str(subject_code)
        row["subjectName"] = subject_name
        row["subject_name"] = subject_name
        row.setdefault("sort_num", subject_id)
        row["auth"] = 1
        row["is_auth"] = True
        row["isAuth"] = True
        rows.append(row)
    return rows


def _load_runtime_teacher_capture(filename: str) -> dict[str, Any] | None:
    path = Path(r"D:\kaifa\steam_fun\runtime\api\teacher") / filename
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _local_stuexam_seed_payloads() -> dict[str, dict[str, Any]]:
    return {
        "practice_list": _load_runtime_teacher_capture("get_cc5f98a56fb8ca22.bin") or {},
        "exam_list": _load_runtime_teacher_capture("get_70f062c3737ff2c7.bin") or {},
        "paper_list": _load_runtime_teacher_capture("get_36b19ebdc7cf774f.bin") or {},
        "question_list": _load_runtime_teacher_capture("get_670e067204b0a87f.bin") or {},
    }


def _local_stuexam_fallback_title(exam_id: int) -> str:
    if exam_id == 228978:
        return "信息素养大赛 2024 复赛 小低组"
    return f"Local Exam {exam_id}"


def _local_stuexam_context(
    store: MirrorStore,
    request: Request,
    request_body: bytes | None = None,
) -> dict[str, Any]:
    submitted = _load_request_payload(request_body or b"")
    exam_id = _parse_int_like(_request_payload_value(request, submitted, "examId", "id", "testExamId", "practiceId"))
    if exam_id is None:
        referer = str(request.headers.get("referer") or "").strip()
        if referer:
            referer_query = parse_qs(urlparse(referer).query)
            for key in ("exam_id", "examId", "id", "practiceId"):
                values = referer_query.get(key) or []
                if not values:
                    continue
                exam_id = _parse_int_like(values[0])
                if exam_id is not None:
                    break
    if exam_id is None:
        exam_stu_record_id = _parse_int_like(_request_payload_value(request, submitted, "examStuRecordId"))
        if exam_stu_record_id and exam_stu_record_id >= 10:
            exam_id = exam_stu_record_id // 10
    if exam_id is None:
        exam_id = 242055
    question_id = _parse_int_like(_request_payload_value(request, submitted, "questionId")) or 63075
    student_context = _student_profile_context(store, request)
    seed = _local_stuexam_seed_payloads()
    exam_rows = (
        (seed.get("exam_list") or {}).get("content", {}).get("examList")
        if isinstance((seed.get("exam_list") or {}).get("content"), dict)
        else []
    )
    practice_rows = (
        (seed.get("practice_list") or {}).get("content", {}).get("examList")
        if isinstance((seed.get("practice_list") or {}).get("content"), dict)
        else []
    )
    paper_rows = (
        (seed.get("paper_list") or {}).get("content", {}).get("paperList")
        if isinstance((seed.get("paper_list") or {}).get("content"), dict)
        else []
    )
    question_rows = (
        (seed.get("question_list") or {}).get("content", {}).get("questionList")
        if isinstance((seed.get("question_list") or {}).get("content"), dict)
        else []
    )

    selected_exam = None
    for source_rows in (exam_rows, practice_rows):
        for row in source_rows or []:
            if _coerce_int((row or {}).get("id")) == exam_id:
                selected_exam = _json_deep_copy(row)
                break
        if selected_exam is not None:
            break
    if selected_exam is None and practice_rows:
        selected_exam = _json_deep_copy(practice_rows[0])
    if selected_exam is None and exam_rows:
        selected_exam = _json_deep_copy(exam_rows[0])
    if not isinstance(selected_exam, dict):
        selected_exam = {
            "id": exam_id,
            "title": _local_stuexam_fallback_title(exam_id),
            "lasttime": 3600,
            "subject_id": 2,
            "is_show_answer": True,
            "show_answer_type": 1,
        }

    selected_exam["id"] = _coerce_int(selected_exam.get("id")) or exam_id
    exam_id = selected_exam["id"]

    paper_id = (
        _coerce_int((selected_exam.get("paperInfo") or {}).get("id"))
        or _coerce_int(selected_exam.get("test_paper_id"))
        or 156584
    )
    selected_paper = None
    for row in paper_rows:
        if _coerce_int((row or {}).get("id")) == paper_id:
            selected_paper = _json_deep_copy(row)
            break
    if selected_paper is None and isinstance(selected_exam.get("paperInfo"), dict):
        selected_paper = _json_deep_copy(selected_exam["paperInfo"])
    if selected_paper is None and paper_rows:
        selected_paper = _json_deep_copy(paper_rows[0])
    if not isinstance(selected_paper, dict):
        selected_paper = {"id": paper_id, "title": selected_exam.get("title") or f"Local Paper {paper_id}"}
    selected_paper["id"] = _coerce_int(selected_paper.get("id")) or paper_id

    selected_questions: list[dict[str, Any]] = []
    for index, row in enumerate(question_rows or []):
        if not isinstance(row, dict):
            continue
        question_row = _json_deep_copy(row)
        question_row["index"] = index
        selected_questions.append(question_row)
    if not selected_questions:
        selected_questions = [
            {
                "id": question_id,
                "type": "1",
                "subject_id": 2,
                "title": "<p>Local mirror fallback question</p>",
                "title_str": "Local mirror fallback question",
                "title_md": "",
                "options": json.dumps(
                    [
                        {"title": "A", "content": "Answer A"},
                        {"title": "B", "content": "Answer B"},
                        {"title": "C", "content": "Answer C"},
                        {"title": "D", "content": "Answer D"},
                    ],
                    ensure_ascii=False,
                ),
                "options_md": json.dumps(
                    [
                        {"title": "A", "content": "Answer A"},
                        {"title": "B", "content": "Answer B"},
                        {"title": "C", "content": "Answer C"},
                        {"title": "D", "content": "Answer D"},
                    ],
                    ensure_ascii=False,
                ),
                "answer": "A",
                "analysis": "Local mirror fallback analysis",
                "analysis_md": "",
                "score": 1,
                "show_type": 1,
                "judge_mode": "manual",
                "index": 0,
            }
        ]

    answer_rows = store.list_local_student_exam_answers(exam_id, stu_id=student_context.get("student_id") or 0)
    answers_by_question_id = {
        _coerce_int(row.get("question_id")): row
        for row in answer_rows
        if isinstance(row, dict) and _coerce_int(row.get("question_id")) is not None
    }

    normalized_questions: list[dict[str, Any]] = []
    for index, question in enumerate(selected_questions):
        question_row = _json_deep_copy(question)
        question_row["id"] = _coerce_int(question_row.get("id")) or (question_id + index)
        question_row["index"] = index
        if question_row.get("subject_id") in (None, ""):
            question_row["subject_id"] = _coerce_int(selected_exam.get("subject_id")) or 2
        if question_row.get("show_type") in (None, ""):
            question_row["show_type"] = 1
        answer_row = answers_by_question_id.get(question_row["id"])
        if answer_row:
            question_row["stu_answer"] = answer_row.get("answer") or ""
            question_row["stuExamQuestionId"] = answer_row.get("stu_exam_question_id")
            question_row["stuExamQuestionInfo"] = {
                "id": answer_row.get("stu_exam_question_id"),
                "answer": answer_row.get("answer") or "",
                "score": answer_row.get("score"),
                "answer_state": "1",
            }
        else:
            question_row["stu_answer"] = ""
            question_row["stuExamQuestionId"] = ""
        normalized_questions.append(question_row)

    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing_run = store.get_local_student_exam_run(exam_id, stu_id=student_context.get("student_id") or 0)
    if existing_run and existing_run.get("started_at"):
        started_at = str(existing_run.get("started_at"))
    else:
        store.upsert_local_student_exam_run(
            exam_id,
            {
                "paper_id": selected_paper.get("id"),
                "title": selected_exam.get("title"),
                "started_at": started_at,
            },
            stu_id=student_context.get("student_id") or 0,
        )

    return {
        "student_context": student_context,
        "seed": seed,
        "exam_id": exam_id,
        "question_id": question_id,
        "exam": selected_exam,
        "paper": selected_paper,
        "questions": normalized_questions,
        "started_at": started_at,
        "system_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _normalize_student_work_row(
    store: MirrorStore,
    row: dict[str, Any],
    *,
    default_subject_code: Any = None,
) -> dict[str, Any]:
    normalized = _json_deep_copy(row)
    subject_code = _coerce_int(
        normalized.get("subject_code")
        or normalized.get("subjectCode")
        or normalized.get("subject_id")
        or normalized.get("subjectId")
        or default_subject_code
    )
    subject_snapshot = _teacher_subject_snapshot(store, str(subject_code or default_subject_code or ""))
    work_id = _coerce_int(normalized.get("id") or normalized.get("workId"))
    if work_id is None:
        work_id = _coerce_int(
            normalized.get("stu_tch_plan_id")
            or normalized.get("stuTchPlanId")
            or normalized.get("student_user_id")
            or normalized.get("stu_user_id")
        ) or 0
    work_url = str(normalized.get("work_url") or normalized.get("workUrl") or "").strip()
    cover_url = str(normalized.get("covers") or normalized.get("coverUrl") or "").strip()
    work_type = _coerce_int(normalized.get("work_type") or normalized.get("workType") or subject_code) or 1
    lesson_id = _coerce_int(
        normalized.get("lessonId")
        or normalized.get("lessionId")
        or normalized.get("lesson_id")
        or normalized.get("curriculum_meterial_id")
        or normalized.get("curriculumMaterialId")
        or normalized.get("stu_tch_plan_id")
    ) or 0
    teaching_plan_id = _coerce_int(
        normalized.get("teaching_plan_id")
        or normalized.get("teachingPlanId")
        or normalized.get("tchPlanId")
        or normalized.get("stu_tch_plan_id")
        or normalized.get("stuTchPlanId")
    ) or 0
    student_id = _coerce_int(
        normalized.get("stu_user_id")
        or normalized.get("stuUserId")
        or normalized.get("student_user_id")
    )
    edu_id = _coerce_int(normalized.get("educational_institution_id") or normalized.get("eduId")) or 0

    normalized["id"] = work_id
    normalized["workId"] = work_id
    normalized["work_url"] = work_url
    normalized["workUrl"] = work_url
    normalized["covers"] = cover_url
    normalized["coverUrl"] = cover_url
    normalized["work_type"] = work_type
    normalized["workType"] = str(work_type)
    if subject_code is not None:
        normalized["subject_code"] = subject_code
        normalized["subjectCode"] = str(subject_code)
    normalized.setdefault("subject_name", subject_snapshot.get("subjectName") or "")
    normalized.setdefault("subjectName", subject_snapshot.get("subjectName") or "")
    normalized["lesson_id"] = lesson_id
    normalized["lessonId"] = lesson_id
    normalized["lessionId"] = lesson_id
    normalized["teaching_plan_id"] = teaching_plan_id
    normalized["teachingPlanId"] = teaching_plan_id
    normalized["tchPlanId"] = teaching_plan_id
    if student_id is not None:
        normalized["stu_user_id"] = student_id
        normalized["stuUserId"] = student_id
        normalized["student_user_id"] = student_id
    normalized["educational_institution_id"] = edu_id
    normalized["eduId"] = edu_id
    return normalized


def _load_cached_student_work_rows(store: MirrorStore, request: Request | None = None) -> list[dict[str, Any]]:
    context = _student_profile_context(store, request)
    current_student_id = context.get("student_id")
    rows_by_id: dict[int, dict[str, Any]] = {}

    for payload in store.load_api_payloads("student", "/api/stu/get/index/tch/work/list"):
        content = payload.get("content") if isinstance(payload.get("content"), dict) else {}
        work_rows = (
            content.get("workList")
            or content.get("tchWorkList")
            or content.get("list")
            or content.get("rows")
            or []
        )
        if not isinstance(work_rows, list):
            continue
        for row in work_rows:
            if not isinstance(row, dict):
                continue
            normalized = _normalize_student_work_row(store, row)
            student_id = _coerce_int(
                normalized.get("stu_user_id")
                or normalized.get("stuUserId")
                or normalized.get("student_user_id")
            )
            if current_student_id is not None and student_id not in (None, current_student_id):
                continue
            row_id = _coerce_int(normalized.get("id"))
            if row_id is None:
                continue
            rows_by_id[row_id] = normalized

    return sorted(
        rows_by_id.values(),
        key=lambda row: (
            str(row.get("update_time") or row.get("updated_time") or row.get("created_time") or ""),
            _coerce_int(row.get("id")) or 0,
        ),
        reverse=True,
    )


def _build_student_work_dataset(store: MirrorStore, request: Request) -> dict[str, Any]:
    requested_subject_code = (
        _first_query_value(request, "subject_code")
        or _first_query_value(request, "subjectCode")
        or _first_query_value(request, "subject_id")
    )
    title_filter = (
        _first_query_value(request, "title")
        or _first_query_value(request, "keyword")
        or _first_query_value(request, "name")
        or ""
    ).strip().lower()
    work_type_filter = _first_query_value(request, "work_type") or _first_query_value(request, "workType")
    page_no, page_size, start = _page_window(request)

    captured_rows = _load_cached_student_work_rows(store, request)
    if captured_rows:
        rows = captured_rows
    else:
        rows = _build_local_work_dataset(
            store,
            request,
            requested_subject_code=requested_subject_code,
            title_filter=title_filter,
            page_no=page_no,
            page_size=max(page_size, 200),
        )["rows"]

    filtered_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = _normalize_student_work_row(store, row, default_subject_code=requested_subject_code)
        subject_candidates = {
            str(value)
            for value in (
                normalized.get("subject_code"),
                normalized.get("subjectCode"),
                normalized.get("work_type"),
                normalized.get("workType"),
            )
            if value not in (None, "")
        }
        if requested_subject_code and requested_subject_code not in subject_candidates:
            continue
        if work_type_filter and work_type_filter not in subject_candidates:
            continue
        if title_filter:
            haystack = " ".join(
                str(value or "")
                for value in (
                    normalized.get("title"),
                    normalized.get("lessonTitle"),
                    normalized.get("realName"),
                    normalized.get("name"),
                )
            ).lower()
            if title_filter not in haystack:
                continue
        filtered_rows.append(normalized)

    page_rows = filtered_rows[start:start + page_size]
    return {
        "rows": page_rows,
        "total": len(filtered_rows),
        "page_no": page_no,
        "page_size": page_size,
        "subjectList": _student_subject_rows(store),
    }


def _build_student_class_rows(store: MirrorStore, request: Request) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    context = _student_profile_context(store, request)
    student_id = _coerce_int(context.get("student_id"))
    student_campus_id = _coerce_int(context.get("campus_id"))
    member_class_ids = _student_member_class_ids(store, student_id)
    teacher_rows, _ = _build_teacher_class_rows(store, request)
    plans_by_class: dict[int, list[dict[str, Any]]] = {}
    for plan in store.list_teaching_plans():
        if not isinstance(plan, dict):
            continue
        class_info = plan.get("classInfo") if isinstance(plan.get("classInfo"), dict) else {}
        class_id = _coerce_int(class_info.get("id") or plan.get("curriculum_class_id"))
        if class_id is None:
            continue
        plans_by_class.setdefault(class_id, []).append(plan)

    subject_catalog = {subject["id"]: subject for subject in _student_subject_rows(store)}
    rows: list[dict[str, Any]] = []
    seen_subject_ids: set[int] = set()

    for row in teacher_rows:
        normalized = _json_deep_copy(row)
        class_id = _coerce_int(normalized.get("id"))
        if member_class_ids and class_id not in member_class_ids:
            continue
        campus_id = _coerce_int(normalized.get("educational_institution_campus_id"))
        if student_campus_id is not None and campus_id not in (None, student_campus_id):
            continue

        class_plans = plans_by_class.get(class_id or -1, [])
        date_values = [
            str(
                plan.get("class_date")
                or plan.get("start_class_date")
                or plan.get("sign_date")
                or ""
            ).strip()
            for plan in class_plans
        ]
        date_values = [value[:10] for value in date_values if value]
        img_urls = normalized.get("img_url_list") if isinstance(normalized.get("img_url_list"), list) else []
        cover_url = str((img_urls[0] if img_urls else "") or "").strip()
        course_count = max(
            _coerce_int(normalized.get("curriculumNum")) or 0,
            _coerce_int(normalized.get("tchPlanNum")) or 0,
            len(class_plans),
        )

        normalized["curriculumInfo"] = {
            "img_url": cover_url,
            "number_of_courses": course_count,
            "numberOfCourses": course_count,
        }
        normalized["start_date"] = min(date_values) if date_values else ""
        normalized["end_date"] = max(date_values) if date_values else ""
        normalized["startDate"] = normalized["start_date"]
        normalized["endDate"] = normalized["end_date"]
        normalized["week_str"] = str(normalized.get("week_str") or "")
        normalized["time_str"] = str(normalized.get("time_str") or "")

        for subject_id in normalized.get("subjectIdList") or []:
            normalized_subject_id = _coerce_int(subject_id)
            if normalized_subject_id is not None:
                seen_subject_ids.add(normalized_subject_id)

        rows.append(normalized)

    rows.sort(
        key=lambda row: (
            str(row.get("name") or "").upper().startswith("AUDIT-"),
            -(max(_coerce_int((row.get("curriculumInfo") or {}).get("number_of_courses")) or 0, 0)),
            str(row.get("start_date") or ""),
            _coerce_int(row.get("id")) or 0,
        )
    )

    user_subject = [
        subject_catalog[subject_id]
        for subject_id in sorted(seen_subject_ids)
        if subject_id in subject_catalog
    ]
    if not user_subject:
        user_subject = _student_subject_rows(store)
    return rows, user_subject


def _build_student_timetable_rows(store: MirrorStore, request: Request) -> dict[str, Any]:
    context = _student_profile_context(store, request)
    student_id = _coerce_int(context.get("student_id")) or 0
    student_campus_id = _coerce_int(context.get("campus_id"))
    member_class_ids = _student_member_class_ids(store, student_id)
    requested_subject_code = (
        _first_query_value(request, "subject_code")
        or _first_query_value(request, "subjectCode")
        or _first_query_value(request, "subject_id")
    )
    class_id_filter = _first_query_value(request, "class_id")
    title_filter = (_first_query_value(request, "title") or "").strip().lower()

    materials_by_id: dict[int, dict[str, Any]] = {}
    for material in store.list_curriculum_materials():
        if not isinstance(material, dict):
            continue
        material_id = _coerce_int(material.get("id"))
        if material_id is not None:
            materials_by_id[material_id] = material

    rows: list[dict[str, Any]] = []
    for row in _build_teacher_teaching_plan_rows(store, request):
        normalized = _json_deep_copy(row)
        class_info = normalized.get("classInfo") if isinstance(normalized.get("classInfo"), dict) else {}
        lesson_info = normalized.get("lessionInfo") if isinstance(normalized.get("lessionInfo"), dict) else {}
        class_id = _coerce_int(class_info.get("id") or normalized.get("curriculum_class_id"))
        campus_id = _coerce_int(
            normalized.get("educational_institution_campus_id")
            or class_info.get("educational_institution_campus_id")
        )
        subject_id = _coerce_int(normalized.get("subject_id"))
        if member_class_ids and class_id not in member_class_ids:
            continue
        if student_campus_id is not None and campus_id not in (None, student_campus_id):
            continue
        if class_id_filter and str(class_id or "") != class_id_filter:
            continue
        if requested_subject_code and requested_subject_code not in {
            str(value)
            for value in (subject_id, normalized.get("subject_id"), normalized.get("subjectCode"))
            if value not in (None, "")
        }:
            continue

        material = materials_by_id.get(_coerce_int(normalized.get("curriculum_meterial_id")) or -1)
        lesson_title = str(
            lesson_info.get("title")
            or normalized.get("title")
            or (material or {}).get("title")
            or ""
        ).strip()
        if title_filter:
            haystack = " ".join(
                part
                for part in (
                    lesson_title,
                    str(class_info.get("name") or ""),
                    str(normalized.get("className") or ""),
                )
                if part
            ).lower()
            if title_filter not in haystack:
                continue

        plan_id = _coerce_int(normalized.get("id")) or 0
        template_info = _teaching_plan_template_info(store, request, teaching_plan_id=plan_id)
        cover_url = _material_asset_url(
            store,
            material,
            (
                "img_url",
                "other_meterial_url",
                "ppt_url",
                "stu_note_url",
                "video_url",
                "teach_template_url",
                "home_template_url",
            ),
        ) or str(lesson_info.get("img_url") or "")
        class_work_url = str(
            template_info.get("classWorkUrl")
            or template_info.get("exampleWorkUrl")
            or _material_asset_url(store, material, ("teach_template_url", "exampal_work_url", "home_template_url"))
            or (material or {}).get("teach_template_url")
            or (material or {}).get("exampal_work_url")
            or (material or {}).get("home_template_url")
            or (material or {}).get("ppt_url")
            or (material or {}).get("video_url")
            or cover_url
            or ""
        ).strip()
        homework_work_url = str(
            template_info.get("homeworkWorkUrl")
            or _material_asset_url(store, material, ("home_template_url", "teach_template_url", "exampal_work_url"))
            or (material or {}).get("home_template_url")
            or (material or {}).get("teach_template_url")
            or (material or {}).get("exampal_work_url")
            or (material or {}).get("ppt_url")
            or (material or {}).get("video_url")
            or cover_url
            or ""
        ).strip()
        sign_date = str(
            normalized.get("class_date")
            or normalized.get("start_class_date")
            or normalized.get("sign_date")
            or ""
        ).strip()
        sign_end_date = str(
            normalized.get("end_class_date")
            or normalized.get("sign_end_date")
            or sign_date
        ).strip()

        enriched_lesson_info = _json_deep_copy(lesson_info)
        if material is not None:
            enriched_lesson_info.setdefault("id", material.get("id"))
            enriched_lesson_info.setdefault("title", material.get("title") or lesson_title)
            enriched_lesson_info.setdefault("desc", material.get("desc") or "")
            enriched_lesson_info.setdefault("img_url", material.get("img_url") or cover_url)
            enriched_lesson_info.setdefault("stu_note_url", material.get("stu_note_url") or "")
            enriched_lesson_info.setdefault("teach_template_url", material.get("teach_template_url") or class_work_url)
            enriched_lesson_info.setdefault("home_template_url", material.get("home_template_url") or homework_work_url)
            enriched_lesson_info.setdefault("ppt_url", material.get("ppt_url") or "")
            enriched_lesson_info.setdefault("video_url", material.get("video_url") or "")
        else:
            enriched_lesson_info.setdefault("title", lesson_title)
            enriched_lesson_info.setdefault("desc", "")
            enriched_lesson_info.setdefault("img_url", cover_url)
            enriched_lesson_info.setdefault("stu_note_url", "")
            enriched_lesson_info.setdefault("teach_template_url", class_work_url)
            enriched_lesson_info.setdefault("home_template_url", homework_work_url)

        stu_tch_plan_id = plan_id * 1000 + (student_id or max(plan_id, 1))
        stu_tch_plan_info = {
            "id": stu_tch_plan_id,
            "stuTchPlanId": stu_tch_plan_id,
            "stu_tch_plan_id": stu_tch_plan_id,
            "student_user_id": student_id,
            "stu_user_id": student_id,
            "sign_state": _coerce_int(normalized.get("sign_state") or normalized.get("signState")) or 0,
            "signState": _coerce_int(normalized.get("sign_state") or normalized.get("signState")) or 0,
            "classWorkState": 1 if class_work_url else 0,
            "homeWorkState": 1 if homework_work_url else 0,
            "classWorkInfo": {"work_url": class_work_url, "workUrl": class_work_url},
            "homeWorkInfo": {"work_url": homework_work_url, "workUrl": homework_work_url},
        }

        normalized["classInfo"] = class_info
        normalized["lessionInfo"] = enriched_lesson_info
        normalized["teachingPlanState"] = normalized.get("teachingPlanState") or _teaching_plan_state_label(normalized)
        normalized["class_covers"] = cover_url
        normalized["class_work_url"] = class_work_url
        normalized["homework_work_url"] = homework_work_url
        normalized["sign_date"] = sign_date
        normalized["sign_end_date"] = sign_end_date
        normalized["signDate"] = sign_date
        normalized["signEndDate"] = sign_end_date
        normalized["classWorkState"] = stu_tch_plan_info["classWorkState"]
        normalized["homeWorkState"] = stu_tch_plan_info["homeWorkState"]
        normalized["stuTchPlanInfo"] = stu_tch_plan_info
        rows.append(normalized)

    page_no, page_size, start = _page_window(request)
    page_rows = rows[start:start + page_size]
    return {
        "tchPlanList": page_rows,
        "stuTchPlanList": page_rows,
        "list": page_rows,
        "rows": page_rows,
        "content": page_rows,
        "total": len(rows),
        "page_no": page_no,
        "page_size": page_size,
        "pageNum": page_no,
        "pageSize": page_size,
    }


def _build_student_index_info_content(store: MirrorStore, request: Request | None = None) -> dict[str, Any]:
    cached_payloads = store.load_api_payloads("student", "/api/stu/get/indexinfo/for/new")
    content = {}
    if cached_payloads:
        cached_content = cached_payloads[0].get("content")
        if isinstance(cached_content, dict):
            content = _json_deep_copy(cached_content)

    if "workNum" not in content:
        content["workNum"] = len(_load_cached_student_work_rows(store, request))
    if "tchWorkNum" not in content:
        content["tchWorkNum"] = len(store.list_teaching_plans())
    if "loginDuration" not in content:
        content["loginDuration"] = 0
    return content


def _build_local_copy_work_content(store: MirrorStore, request: Request, payload: Any) -> dict[str, Any]:
    page_no = _parse_int_like(_request_payload_value(request, payload, "page_no")) or 1
    page_size = _parse_int_like(_request_payload_value(request, payload, "page_size")) or 20
    requested_subject_code = _request_payload_value(request, payload, "subject_code", "subjectCode")
    work_type = _parse_int_like(_request_payload_value(request, payload, "work_type")) or 1
    current_work_id = _parse_int_like(_request_payload_value(request, payload, "work_id"))
    dataset = _build_local_work_dataset(
        store,
        request,
        requested_subject_code=requested_subject_code,
        title_filter=str(_request_payload_value(request, payload, "title") or ""),
        page_no=page_no,
        page_size=page_size,
    )
    rows = [row for row in dataset["rows"] if _parse_int_like(row.get("id")) != current_work_id]
    teacher_user_info = _teacher_user_info(store)
    teacher_name = str(
        teacher_user_info.get("realName")
        or teacher_user_info.get("realname")
        or teacher_user_info.get("userRealname")
        or teacher_user_info.get("name")
        or "Local Mirror Teacher"
    ).strip()
    teacher_headimg_url = str(
        teacher_user_info.get("userImageUrl")
        or teacher_user_info.get("headimgUrl")
        or teacher_user_info.get("headimg_url")
        or "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png"
    ).strip()
    teacher_row_id = (_parse_int_like(dataset.get("lesson_id")) or 1) * 100000 + 1
    teacher_work = {
        "id": teacher_row_id,
        "workId": teacher_row_id,
        "title": dataset["lesson_title"],
        "covers": dataset["lesson_info"].get("covers") or "",
        "work_url": dataset["lesson_info"].get("workUrl") or "",
        "workUrl": dataset["lesson_info"].get("workUrl") or "",
        "work_type": work_type,
        "workType": str(work_type),
        "headImgUrl": teacher_headimg_url,
        "headimg_url": teacher_headimg_url,
        "name": teacher_name,
        "realName": teacher_name,
    }
    return {
        "workList": rows,
        "tchLessonWorkInfo": teacher_work,
        "tchLeesonWorkInfo": teacher_work,
        "total": len(rows),
        "page_no": page_no,
        "page_size": page_size,
    }


def _parse_curriculum_id_from_url(url: str) -> int | None:
    query = parse_qs(urlparse(url).query)
    values = query.get("curriculum_id") or []
    if not values:
        return None
    value = values[0].strip()
    if value.isdigit():
        return int(value)
    return None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text or not text.isdigit():
        return None
    return int(text)


def _coerce_number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    if value is None:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).strip())
    if not match:
        return None
    number = float(match.group(0))
    if number.is_integer():
        return int(number)
    return number


def _localize_mirrored_url(value: Any, *, default: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return default
    if text.startswith(("/_external/", "/", "data:")):
        return text
    if text.startswith(("http://", "https://", "//")):
        return rewrite_external_urls(text)
    return text


def _merge_dict_defaults(current: Any, defaults: dict[str, Any]) -> dict[str, Any]:
    merged = _json_deep_copy(current) if isinstance(current, dict) else {}
    for key, value in defaults.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _merge_dict_defaults(existing, value)
            continue
        if existing in (None, "", []):
            merged[key] = _json_deep_copy(value)
    return merged


def _normalize_curriculum_storage_fields(
    row: dict[str, Any],
    material_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    total_storage: int | float | None = None
    used_storage: int | float | None = None
    remain_storage: int | float | None = None

    def collect(container: Any) -> None:
        nonlocal total_storage, used_storage, remain_storage
        if not isinstance(container, dict):
            return
        if total_storage is None:
            for key in ("total_storage", "totalStorage", "storageSize", "storage_size", "storage"):
                candidate = _coerce_number(container.get(key))
                if candidate is not None:
                    total_storage = candidate
                    break
        if used_storage is None:
            for key in ("useStorage", "use_storage", "usedStorage", "occupySpace"):
                candidate = _coerce_number(container.get(key))
                if candidate is not None:
                    used_storage = candidate
                    break
        if remain_storage is None:
            for key in ("remainTraffic", "remain_storage", "remainStorage"):
                candidate = _coerce_number(container.get(key))
                if candidate is not None:
                    remain_storage = candidate
                    break

    collect(row)
    if isinstance(material_rows, list):
        for material in material_rows:
            collect(material)

    if total_storage is None:
        total_storage = 0
    if used_storage is None:
        used_storage = 0
    if remain_storage is None:
        remain_storage = total_storage - used_storage
    if isinstance(remain_storage, (int, float)) and remain_storage < 0:
        remain_storage = 0

    row["total_storage"] = total_storage
    row["totalStorage"] = total_storage
    row["storage"] = total_storage
    row["storage_size"] = total_storage
    row["storageSize"] = total_storage
    row["lessionTotalStorage"] = total_storage
    row["lessonTotalStorage"] = total_storage
    row["useStorage"] = used_storage
    row["use_storage"] = used_storage
    row["usedStorage"] = used_storage
    row["occupySpace"] = used_storage
    row["remainTraffic"] = remain_storage
    row["remain_storage"] = remain_storage
    row["remainStorage"] = remain_storage
    return row


def _is_placeholder_name(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    normalized = text.replace(" ", "")
    return bool(normalized) and all(char in PLACEHOLDER_NAME_CHARS for char in normalized)


def _student_display_name(student: dict[str, Any], *, default_id: Any = None) -> str:
    for key in ("realname", "realName"):
        value = str(student.get(key) or "").strip()
        if value and not _is_placeholder_name(value):
            return value

    for key in ("name", "username", "account"):
        value = str(student.get(key) or "").strip()
        if value and not _is_placeholder_name(value):
            return value

    for key in ("realname", "realName", "name", "username"):
        value = str(student.get(key) or "").strip()
        if value:
            return value

    student_id = _coerce_int(student.get("id") or default_id)
    if student_id is not None:
        return f"Student {student_id}"
    return "Local Mirror Student"


def _append_unique_int(target: list[int], value: Any) -> None:
    if isinstance(value, dict):
        for key in ("dept_id", "id", "eduCampusId", "educationalInstitutionCampusId", "educational_institution_campus_id", "campusId"):
            if key in value:
                _append_unique_int(target, value[key])
                return
        return

    normalized = _coerce_int(value)
    if normalized is not None and normalized not in target:
        target.append(normalized)


def _append_unique_text(target: list[str], value: Any) -> None:
    if value in (None, ""):
        return
    normalized = str(value).strip()
    if normalized and normalized not in target:
        target.append(normalized)


def _teacher_school_info(store: MirrorStore, profile_name: str = "teacher") -> dict[str, Any]:
    teacher_profile = store.get_profile(profile_name) or store.get_profile("teacher") or {}
    school_info = (teacher_profile.get("fresh_auth") or {}).get("schoolInfo") or {}
    return school_info if isinstance(school_info, dict) else {}


def _teacher_user_info(store: MirrorStore, profile_name: str = "teacher") -> dict[str, Any]:
    teacher_profile = store.get_profile(profile_name) or store.get_profile("teacher") or {}
    user_info = (teacher_profile.get("fresh_auth") or {}).get("userInfo") or {}
    return user_info if isinstance(user_info, dict) else {}


_TEACHER_CAMPUS_IDS_CACHE: dict[str, list[int]] = {}

def _teacher_selected_school_ids(store: MirrorStore, profile_name: str = "teacher") -> list[int]:
    cached = _TEACHER_CAMPUS_IDS_CACHE.get(profile_name)
    if cached is not None:
        return cached
    campus_ids: list[int] = []
    teacher_profile = store.get_profile(profile_name) or store.get_profile("teacher") or {}
    user_state = (teacher_profile.get("vuex_state") or {}).get("user") or {}

    selected_schools = user_state.get("selected_schools")
    if isinstance(selected_schools, list):
        for item in selected_schools:
            _append_unique_int(campus_ids, item)
    elif selected_schools not in (None, ""):
        _append_unique_int(campus_ids, selected_schools)

    for campus in store.list_user_campuses():
        if isinstance(campus, dict):
            _append_unique_int(campus_ids, campus)

    for source in (_teacher_school_info(store, profile_name), _teacher_user_info(store, profile_name)):
        for key in (
            "eduCampusId",
            "educationalInstitutionCampusId",
            "educational_institution_campus_id",
            "campusId",
            "dept_id",
        ):
            _append_unique_int(campus_ids, source.get(key))

    for entry in store.list_campus_curriculum_auths():
        if not isinstance(entry, dict):
            continue
        _append_unique_int(campus_ids, entry.get("educational_institution_campus_id"))
        curriculum_info = entry.get("curriculumInfo") or {}
        if isinstance(curriculum_info, dict):
            _append_unique_int(campus_ids, curriculum_info.get("educational_institution_campus_id"))

    for plan in store.list_teaching_plans():
        if not isinstance(plan, dict):
            continue
        _append_unique_int(campus_ids, plan.get("educational_institution_campus_id"))
        class_info = plan.get("classInfo") or {}
        if isinstance(class_info, dict):
            _append_unique_int(campus_ids, class_info.get("educational_institution_campus_id"))

    _TEACHER_CAMPUS_IDS_CACHE[profile_name] = campus_ids
    return campus_ids


def _teacher_primary_campus_id(store: MirrorStore, profile_name: str = "teacher") -> int | None:
    campus_ids = _teacher_selected_school_ids(store, profile_name)
    return campus_ids[0] if campus_ids else None


def _teacher_primary_campus_name(store: MirrorStore, profile_name: str = "teacher") -> str:
    primary_campus_id = _teacher_primary_campus_id(store, profile_name)
    if primary_campus_id is not None:
        for campus in store.list_user_campuses():
            if not isinstance(campus, dict):
                continue
            campus_id = _coerce_int(campus.get("dept_id") or campus.get("id"))
            if campus_id == primary_campus_id and campus.get("campusName"):
                return str(campus["campusName"])

    school_info = _teacher_school_info(store, profile_name)
    for key in ("campusName", "name"):
        value = school_info.get(key)
        if value not in (None, ""):
            return str(value)
    return "榛樿鏍″尯"


def _hydrate_teacher_school_info(
    store: MirrorStore,
    source: Any = None,
    profile_name: str = "teacher",
) -> dict[str, Any]:
    normalized = json.loads(json.dumps(source, ensure_ascii=False)) if isinstance(source, dict) else {}
    campus_id = _teacher_primary_campus_id(store, profile_name)
    campus_name = _teacher_primary_campus_name(store, profile_name)
    display_name = str(
        normalized.get("name")
        or normalized.get("eduName")
        or campus_name
        or "Mirror School"
    ).strip()
    logo_img_url = _localize_mirrored_url(
        normalized.get("logo_img_url") or normalized.get("logoImgUrl") or normalized.get("img_url"),
        default=DEFAULT_HOMEPAGE_AVATAR_URL,
    )
    modal_img_url = _localize_mirrored_url(
        normalized.get("modal_img_url") or normalized.get("modalImgUrl"),
        default=DEFAULT_HOMEPAGE_MODAL_URL,
    )

    if campus_id is not None:
        normalized.setdefault("eduCampusId", campus_id)
        normalized.setdefault("educationalInstitutionCampusId", campus_id)
        normalized.setdefault("educational_institution_campus_id", campus_id)
        normalized.setdefault("campusId", campus_id)
    if campus_name:
        normalized.setdefault("campusName", campus_name)
    normalized.setdefault("name", display_name)
    normalized.setdefault("eduName", normalized.get("name") or display_name)
    theme_color = normalized.get("theme_color") or normalized.get("themeColor") or "#1778FF"
    normalized.setdefault("theme_color", theme_color)
    normalized.setdefault("themeColor", theme_color)
    normalized.setdefault("logo_img_url", logo_img_url)
    normalized.setdefault("logoImgUrl", logo_img_url)
    normalized.setdefault("img_url", logo_img_url)
    normalized.setdefault("modal_img_url", modal_img_url)
    normalized.setdefault("modalImgUrl", modal_img_url)
    normalized.setdefault("is_encryption", False)
    return normalized


def _hydrate_teacher_user_info(
    store: MirrorStore,
    source: Any = None,
    profile_name: str = "teacher",
) -> dict[str, Any]:
    normalized = json.loads(json.dumps(source, ensure_ascii=False)) if isinstance(source, dict) else {}
    campus_id = _teacher_primary_campus_id(store, profile_name)
    campus_name = _teacher_primary_campus_name(store, profile_name)
    profile = store.get_profile(profile_name) or store.get_profile("teacher") or {}
    fallback_name = str(
        normalized.get("realName")
        or normalized.get("realname")
        or normalized.get("userRealname")
        or normalized.get("name")
        or profile.get("username")
        or "Local Mirror Teacher"
    ).strip()
    headimg_url = _localize_mirrored_url(
        normalized.get("userImageUrl") or normalized.get("headimgUrl") or normalized.get("headimg_url"),
        default=DEFAULT_HOMEPAGE_AVATAR_URL,
    )

    if campus_id is not None:
        normalized.setdefault("eduCampusId", campus_id)
        normalized.setdefault("educationalInstitutionCampusId", campus_id)
        normalized.setdefault("educational_institution_campus_id", campus_id)
        normalized.setdefault("campusId", campus_id)
        normalized.setdefault("dept_id", campus_id)
    if campus_name:
        normalized.setdefault("campusName", campus_name)
    if normalized.get("realname") in (None, "") and normalized.get("realName") not in (None, ""):
        normalized["realname"] = normalized["realName"]
    if normalized.get("realName") in (None, "") and normalized.get("realname") not in (None, ""):
        normalized["realName"] = normalized["realname"]
    normalized.setdefault("realname", fallback_name)
    normalized.setdefault("realName", normalized.get("realname") or fallback_name)
    normalized["userImageUrl"] = headimg_url
    normalized["headimgUrl"] = headimg_url
    normalized["headimg_url"] = headimg_url
    return normalized


def _build_student_homepage_user_info(store: MirrorStore, request: Request | None = None) -> dict[str, Any]:
    context = _student_profile_context(store, request)
    normalized = _json_deep_copy(context.get("user_info")) if isinstance(context.get("user_info"), dict) else {}
    display_name = str(context.get("display_name") or context.get("account_name") or "Local Mirror Student").strip()
    account_name = str(context.get("account_name") or display_name).strip()
    student_id = _coerce_int(context.get("student_id"))
    campus_id = _coerce_int(context.get("campus_id"))
    avatar_url = _localize_mirrored_url(
        ((context.get("stu_base_info") or {}).get("headimgUrl"))
        or ((context.get("stu_base_info") or {}).get("headimg_url"))
        or ((context.get("stu_user_info") or {}).get("headimgUrl"))
        or ((context.get("stu_user_info") or {}).get("headimg_url"))
        or normalized.get("headimgUrl")
        or normalized.get("headimg_url"),
        default=DEFAULT_HOMEPAGE_AVATAR_URL,
    )

    if student_id is not None:
        normalized.setdefault("id", student_id)
    if campus_id is not None:
        normalized.setdefault("eduCampusId", campus_id)
    normalized.setdefault("name", account_name)
    normalized.setdefault("username", account_name)
    normalized.setdefault("realName", display_name)
    normalized.setdefault("realname", display_name)
    normalized["userImageUrl"] = avatar_url
    normalized["headimgUrl"] = avatar_url
    normalized["headimg_url"] = avatar_url

    stu_user_info = normalized.get("stuUserInfo")
    if not isinstance(stu_user_info, dict):
        stu_user_info = {}
        normalized["stuUserInfo"] = stu_user_info
    if student_id is not None:
        stu_user_info.setdefault("id", student_id)
    if campus_id is not None:
        stu_user_info.setdefault("eduCampusId", campus_id)
    stu_user_info.setdefault("name", account_name)
    stu_user_info.setdefault("realName", display_name)
    stu_user_info.setdefault("realname", display_name)
    stu_user_info["userImageUrl"] = avatar_url
    stu_user_info["headimgUrl"] = avatar_url
    stu_user_info["headimg_url"] = avatar_url

    stu_base_info = stu_user_info.get("stuUserInfo")
    if not isinstance(stu_base_info, dict):
        stu_base_info = {}
        stu_user_info["stuUserInfo"] = stu_base_info
    if student_id is not None:
        stu_base_info.setdefault("id", student_id)
    if campus_id is not None:
        stu_base_info.setdefault("eduCampusId", campus_id)
    stu_base_info.setdefault("realName", display_name)
    stu_base_info.setdefault("realname", display_name)
    stu_base_info["userImageUrl"] = avatar_url
    stu_base_info["headimgUrl"] = avatar_url
    stu_base_info["headimg_url"] = avatar_url
    return normalized


def _build_homepage_content(store: MirrorStore, request: Request) -> dict[str, Any]:
    resolved_profile = _resolve_profile(store, request)
    request_profile = _profile_role(
        resolved_profile["profile_name"],
        resolved_profile,
    ) if resolved_profile else _infer_profile_from_request(request)
    if request_profile == "student":
        student_context = _student_profile_context(store, request)
        school_source = (
            student_context.get("school_info")
            if isinstance(student_context.get("school_info"), dict)
            else _teacher_school_info(store)
        )
        school_info = _hydrate_teacher_school_info(store, school_source)
        user_info = _build_student_homepage_user_info(store, request)
    else:
        school_info = _hydrate_teacher_school_info(store, _teacher_school_info(store))
        user_info = _hydrate_teacher_user_info(store, _teacher_user_info(store))

    school_name = str(
        school_info.get("eduName")
        or school_info.get("name")
        or school_info.get("campusName")
        or _teacher_primary_campus_name(store)
        or "Mirror School"
    ).strip()
    logo_img_url = _localize_mirrored_url(
        user_info.get("userImageUrl")
        or user_info.get("headimgUrl")
        or user_info.get("headimg_url")
        or school_info.get("logo_img_url")
        or school_info.get("logoImgUrl")
        or school_info.get("img_url"),
        default=DEFAULT_HOMEPAGE_AVATAR_URL,
    )
    modal_img_url = _localize_mirrored_url(
        school_info.get("modal_img_url") or school_info.get("modalImgUrl"),
        default=DEFAULT_HOMEPAGE_MODAL_URL,
    )
    homepage = {
        "logo_img_url": logo_img_url,
        "logoImgUrl": logo_img_url,
        "modal_img_url": modal_img_url,
        "modalImgUrl": modal_img_url,
        "is_show_copy_right": False,
        "schoolName": school_name,
        "eduName": school_name,
    }
    school_defaults = {
        "name": school_name,
        "eduName": school_name,
        "logo_img_url": logo_img_url,
        "logoImgUrl": logo_img_url,
        "img_url": logo_img_url,
        "modal_img_url": modal_img_url,
        "modalImgUrl": modal_img_url,
    }
    return {
        "schoolInfo": _merge_dict_defaults(school_info, school_defaults),
        "userInfo": _json_deep_copy(user_info),
        "homepageData": {"homepage": _json_deep_copy(homepage)},
        "homepage": _json_deep_copy(homepage),
        "imgUrl": logo_img_url,
    }


def _teacher_state_with_route_context(
    store: MirrorStore,
    profile_name: str,
    *,
    route_key: str | None = None,
) -> dict[str, Any] | None:
    teacher_profile = store.get_profile(profile_name) or store.get_profile("teacher") or {}
    vuex_state = teacher_profile.get("vuex_state")
    if not isinstance(vuex_state, dict):
        return None

    normalized_state = json.loads(json.dumps(vuex_state, ensure_ascii=False))
    normalized_permissions = _teacher_permission_tree(store, profile_name)
    normalized_admin_permissions = _teacher_admin_permissions(store, profile_name)
    teacher_school_info = _hydrate_teacher_school_info(
        store,
        _teacher_school_info(store, profile_name),
        profile_name,
    )
    teacher_user_info = _hydrate_teacher_user_info(
        store,
        _teacher_user_info(store, profile_name),
        profile_name,
    )
    selected_school_ids = _teacher_selected_school_ids(store, profile_name)
    user_state = normalized_state.get("user")
    if isinstance(user_state, dict):
        token = teacher_profile.get("token")
        if token and not user_state.get("token"):
            user_state["token"] = token
        if token and not user_state.get("adminToken"):
            user_state["adminToken"] = token
        if teacher_profile.get("username") and not user_state.get("adminUserName"):
            user_state["adminUserName"] = teacher_profile["username"]
        user_state["permisionList"] = _json_deep_copy(normalized_permissions)
        user_state["adminpermisionList"] = _json_deep_copy(normalized_admin_permissions)
        if "isSuperAdmin" not in user_state:
            user_state["isSuperAdmin"] = False
        if selected_school_ids and not user_state.get("selected_schools"):
            user_state["selected_schools"] = selected_school_ids

        existing_school_info = user_state.get("schoolInfo")
        if isinstance(existing_school_info, dict):
            merged_school_info = _json_deep_copy(existing_school_info)
            for key, value in teacher_school_info.items():
                if merged_school_info.get(key) in (None, "") and value not in (None, ""):
                    merged_school_info[key] = value
            user_state["schoolInfo"] = _hydrate_teacher_school_info(store, merged_school_info, profile_name)
        else:
            user_state["schoolInfo"] = _json_deep_copy(teacher_school_info)

        existing_user_info = user_state.get("userInfo")
        if isinstance(existing_user_info, dict):
            merged_user_info = _json_deep_copy(existing_user_info)
            for key, value in teacher_user_info.items():
                if merged_user_info.get(key) in (None, "") and value not in (None, ""):
                    merged_user_info[key] = value
            user_state["userInfo"] = _hydrate_teacher_user_info(store, merged_user_info, profile_name)
        else:
            user_state["userInfo"] = _json_deep_copy(teacher_user_info)

        if route_key and route_key.startswith("/exam-stu"):
            student_context = _student_profile_context(store)
            if teacher_profile.get("username") and not user_state.get("username"):
                user_state["username"] = teacher_profile["username"]
            if not user_state.get("adminUserName") and teacher_profile.get("username"):
                user_state["adminUserName"] = teacher_profile["username"]
            existing_user_info = user_state.get("userInfo")
            if not isinstance(existing_user_info, dict):
                existing_user_info = {}
            merged_student_user_info = _json_deep_copy(existing_user_info)
            merged_student_user_info["stuUserInfo"] = {
                "id": student_context.get("student_id") or 0,
                "name": student_context.get("account_name") or "",
                "eduCampusId": student_context.get("campus_id") or 0,
                "zoneAuth": True,
                "testAuth": True,
                "ojAuth": True,
                "ojAnalysisAuth": True,
                "ojTestcaseAuth": True,
                "stuNoteAuth": True,
                "pAuth": True,
                "pauth": True,
                "stuUserInfo": {
                    "id": student_context.get("student_id") or 0,
                    "realName": student_context.get("display_name") or "",
                    "eduId": student_context.get("school_id") or 0,
                    "eduCampusId": student_context.get("campus_id") or 0,
                    "schoolName": student_context.get("school_info", {}).get("name") or "",
                    "sex": student_context.get("stu_base_info", {}).get("sex") or "M",
                    "grade": student_context.get("stu_base_info", {}).get("grade"),
                    "parentAPhoneNum": student_context.get("stu_base_info", {}).get("parentAPhoneNum") or "",
                },
                "realName": student_context.get("display_name") or "",
                "realname": student_context.get("display_name") or "",
            }
            user_state["userInfo"] = merged_student_user_info
            user_state["username"] = student_context.get("account_name") or user_state.get("username") or ""
            user_state["identity"] = 2
    return normalized_state


def _student_state_with_route_context(
    store: MirrorStore,
    profile_name: str = "student",
    *,
    route_key: str | None = None,
    request: Request | None = None,
) -> dict[str, Any] | None:
    student_profile = store.get_profile(profile_name) or store.get_profile("student") or {}
    vuex_state = student_profile.get("vuex_state")
    if not isinstance(vuex_state, dict):
        return None

    normalized_state = json.loads(json.dumps(vuex_state, ensure_ascii=False))
    student_context = _student_profile_context(store, request)
    school_source = (
        student_context.get("school_info")
        if isinstance(student_context.get("school_info"), dict)
        else _teacher_school_info(store, profile_name)
    )
    student_school_info = _hydrate_teacher_school_info(store, school_source, profile_name)
    student_user_info = _build_student_homepage_user_info(store, request)
    user_state = normalized_state.get("user")
    if not isinstance(user_state, dict):
        user_state = {}
        normalized_state["user"] = user_state

    token = student_profile.get("token")
    if token and not user_state.get("token"):
        user_state["token"] = token
    if "permisionList" not in user_state or not isinstance(user_state.get("permisionList"), list):
        user_state["permisionList"] = []

    existing_school_info = user_state.get("schoolInfo")
    if isinstance(existing_school_info, dict):
        user_state["schoolInfo"] = _hydrate_teacher_school_info(
            store,
            _merge_dict_defaults(existing_school_info, student_school_info),
            profile_name,
        )
    else:
        user_state["schoolInfo"] = _json_deep_copy(student_school_info)

    existing_user_info = user_state.get("userInfo")
    if isinstance(existing_user_info, dict):
        user_state["userInfo"] = _merge_dict_defaults(existing_user_info, student_user_info)
    else:
        user_state["userInfo"] = _json_deep_copy(student_user_info)

    if student_context.get("account_name") and not user_state.get("username"):
        user_state["username"] = student_context["account_name"]
    user_state["identity"] = 2
    return normalized_state


def _build_teacher_auth_bootstrap(
    store: MirrorStore,
    profile_name: str = "teacher",
    *,
    route_key: str | None = None,
) -> str | None:
    normalized_state = _teacher_state_with_route_context(store, profile_name, route_key=route_key)
    if not isinstance(normalized_state, dict):
        return None

    serialized = json.dumps(normalized_state, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (
        "<script>"
        "(function(){"
        f"var data={serialized};"
        "try{localStorage.setItem('vuex',JSON.stringify(data));}catch(e){}"
        f"try{{sessionStorage.setItem('mirror_profile',{json.dumps(profile_name, ensure_ascii=False)});}}catch(e){{}}"
        "}());"
        "</script>"
    )


def _build_student_auth_bootstrap(
    store: MirrorStore,
    profile_name: str = "student",
    *,
    route_key: str | None = None,
    request: Request | None = None,
) -> str | None:
    normalized_state = _student_state_with_route_context(store, profile_name, route_key=route_key, request=request)
    if not isinstance(normalized_state, dict):
        return None

    serialized = json.dumps(normalized_state, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (
        "<script>"
        "(function(){"
        f"var data={serialized};"
        "try{localStorage.setItem('vuex',JSON.stringify(data));}catch(e){}"
        f"try{{sessionStorage.setItem('mirror_profile',{json.dumps(profile_name, ensure_ascii=False)});}}catch(e){{}}"
        "}());"
        "</script>"
    )


def _build_teacher_session_bootstrap(
    store: MirrorStore,
    request: Request,
    profile_name: str = "teacher",
) -> str | None:
    material = _resolve_teacher_curriculum_material(store, request)
    if material is None:
        return None
    curr_mat_id = int(material.get("id") or 0)
    if curr_mat_id <= 0:
        return None

    teacher_profile = store.get_profile(profile_name) or store.get_profile("teacher") or {}
    teacher_fresh_auth = teacher_profile.get("fresh_auth") or {}
    teacher_school_info = _hydrate_teacher_school_info(
        store,
        teacher_fresh_auth.get("schoolInfo") or {},
        profile_name,
    )
    tch_plan_id = _extract_teaching_plan_id_from_request(request) or 999999
    curriculum_id = material.get("curriculum_id")
    class_id = _first_query_value(request, "classid")
    edu_campus_id = _first_query_value(request, "eduCampusId")
    if not edu_campus_id:
        fallback_campus_id = (
            teacher_school_info.get("eduCampusId")
            or teacher_school_info.get("educationalInstitutionCampusId")
            or _teacher_primary_campus_id(store, profile_name)
        )
        if fallback_campus_id not in (None, ""):
            edu_campus_id = str(fallback_campus_id)
    teaching_plan_state = _first_query_value(request, "teachingPlanState") or material.get("teachingPlanState") or "Not Started"
    end_class_date = _first_query_value(request, "end_class_date") or material.get("end_class_date") or ""
    class_name = _first_query_value(request, "className") or material.get("className") or ""
    teaching_plan_overlay = store.get_teaching_plan_overlay(tch_plan_id) or {}

    classroom = {
        "id": tch_plan_id,
        "curriculum_meterial_id": curr_mat_id,
        "curriculum_class_id": int(class_id) if class_id and class_id.isdigit() else 0,
        "educational_institution_campus_id": int(edu_campus_id) if edu_campus_id and edu_campus_id.isdigit() else 0,
        "subject_id": material.get("subject_id") or 0,
        "curriculum_id": curriculum_id or 0,
        "className": class_name,
        "lessionTitle": material.get("title") or "",
        "teachingPlanState": teaching_plan_state,
        "end_class_date": end_class_date,
        "oj_analysis_auth": (
            bool(teaching_plan_overlay.get("oj_analysis_auth"))
            if teaching_plan_overlay.get("oj_analysis_auth") is not None
            else False
        ),
        "oj_analysis_TEST": (
            bool(teaching_plan_overlay.get("test_case_auth"))
            if teaching_plan_overlay.get("test_case_auth") is not None
            else True
        ),
        "zone_auth": (
            bool(teaching_plan_overlay.get("zone_auth"))
            if teaching_plan_overlay.get("zone_auth") is not None
            else bool(teacher_school_info.get("stuZoneAuth"))
        ),
        "editor_showhint_auth": (
            bool(teaching_plan_overlay.get("editor_showhint_auth"))
            if teaching_plan_overlay.get("editor_showhint_auth") is not None
            else True
        ),
    }
    teacher_plan_list = [classroom]
    payload = {
        "Classroom": classroom,
        "teacherPlanList": teacher_plan_list,
        "subject_id": str(material.get("subject_id") or ""),
    }
    serialized = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    compact_serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (
        "<script>"
        "(function(){"
        f"var data={serialized};"
        "try{sessionStorage.setItem('Classroom',JSON.stringify(data.Classroom));}catch(e){}"
        "try{sessionStorage.setItem('teacherPlanList',JSON.stringify(data.teacherPlanList));}catch(e){}"
        "try{sessionStorage.setItem('subject_id',String(data.subject_id||''));}catch(e){}"
        f"/*{compact_serialized}*/"
        "}());"
        "</script>"
    )


def _build_student_session_bootstrap(
    store: MirrorStore,
    request: Request,
    profile_name: str = "student",
) -> str | None:
    homepage_content = _build_homepage_content(store, request)
    if not isinstance(homepage_content, dict):
        return None

    school_info_payload = _json_deep_copy(homepage_content)
    school_info = school_info_payload.get("schoolInfo")
    if isinstance(school_info, dict):
        school_info_payload["schoolInfo"] = _hydrate_teacher_school_info(store, school_info, profile_name)

    serialized = json.dumps(school_info_payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (
        "<script>"
        "(function(){"
        f"var data={serialized};"
        "var homepage=((data.homepageData||{}).homepage)||data.homepage||{};"
        "try{sessionStorage.setItem('schoolInfo',JSON.stringify(data));}catch(e){}"
        "try{sessionStorage.setItem('homepage',homepage.is_show_copy_right);}catch(e){}"
        "}());"
        "</script>"
    )


def _build_teacher_homepage_session_bootstrap(
    store: MirrorStore,
    request: Request,
    profile_name: str = "teacher",
) -> str | None:
    homepage_content = _build_homepage_content(store, request)
    if not isinstance(homepage_content, dict):
        return None

    school_info_payload = _json_deep_copy(homepage_content)
    school_info = school_info_payload.get("schoolInfo")
    if isinstance(school_info, dict):
        school_info_payload["schoolInfo"] = _hydrate_teacher_school_info(store, school_info, profile_name)

    serialized = json.dumps(school_info_payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (
        "<script>"
        "(function(){"
        f"var data={serialized};"
        "var homepage=((data.homepageData||{}).homepage)||data.homepage||{};"
        "try{sessionStorage.setItem('schoolInfo',JSON.stringify(data));}catch(e){}"
        "try{sessionStorage.setItem('homepage',homepage.is_show_copy_right);}catch(e){}"
        "}());"
        "</script>"
    )


def _build_class_detail_bootstrap(
    store: MirrorStore,
    request: Request,
) -> str | None:
    route_key = _normalize_route_path(request.url.path)
    if route_key != "/school-home-page/class-management1/divide-class1":
        return None

    class_id = _extract_class_id_from_request(request)
    if class_id is None:
        return None

    class_row = store.find_class(class_id)
    if not isinstance(class_row, dict):
        return None

    class_student_payload = store.get_class_student_payload(class_id) or {}
    student_rows = class_student_payload.get("studentList") if isinstance(class_student_payload, dict) else []
    student_total_num = len(student_rows) if isinstance(student_rows, list) else 0
    signed_count = sum(
        1
        for plan in _plan_rows_for_class(store, class_id)
        if _coerce_int((plan or {}).get("sign_state")) == 1
    )
    bootstrap_row = _build_class_list_row_from_teacher_row(
        class_row,
        student_total_num=student_total_num,
        sign_num=signed_count,
    )
    serialized = json.dumps(bootstrap_row, ensure_ascii=False).replace("</", "<\\/")
    compact_serialized = json.dumps(bootstrap_row, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (
        "<script>"
        "(function(){"
        f"var data={serialized};"
        "try{sessionStorage.setItem('courseArranging',JSON.stringify(data));}catch(e){}"
        f"/*{compact_serialized}*/"
        "}());"
        "</script>"
    )


def _build_route_bootstrap(
    store: MirrorStore,
    preferred_profile: str | None,
    request: Request,
    route_key: str,
) -> str | None:
    if _is_login_route(route_key):
        return (
            "<script>"
            "(function(){"
            "try{localStorage.removeItem('vuex');}catch(e){}"
            "try{sessionStorage.removeItem('mirror_profile');}catch(e){}"
            "try{sessionStorage.removeItem('schoolInfo');}catch(e){}"
            "try{sessionStorage.removeItem('homepage');}catch(e){}"
            "try{sessionStorage.removeItem('Classroom');}catch(e){}"
            "try{sessionStorage.removeItem('teacherPlanList');}catch(e){}"
            "try{sessionStorage.removeItem('subject_id');}catch(e){}"
            "try{sessionStorage.removeItem('courseArranging');}catch(e){}"
            "try{document.cookie='mirror_profile=; Max-Age=0; path=/; SameSite=Lax';}catch(e){}"
            "}());"
            "</script>"
        )

    bootstrap_profile_name = preferred_profile
    if not bootstrap_profile_name:
        return None
    profile_role = _profile_role(bootstrap_profile_name, store.get_profile(bootstrap_profile_name))
    if profile_role not in {"admin", "teacher", "student"}:
        return None

    scripts: list[str] = []
    if _is_teacher_like_role(profile_role):
        teacher_auth_bootstrap = _build_teacher_auth_bootstrap(
            store,
            bootstrap_profile_name,
            route_key=route_key,
        )
        if teacher_auth_bootstrap:
            scripts.append(teacher_auth_bootstrap)
        teacher_homepage_session_bootstrap = _build_teacher_homepage_session_bootstrap(
            store,
            request,
            bootstrap_profile_name,
        )
        if teacher_homepage_session_bootstrap:
            scripts.append(teacher_homepage_session_bootstrap)
        if _should_bootstrap_teacher_context(route_key):
            teacher_session_bootstrap = _build_teacher_session_bootstrap(store, request, bootstrap_profile_name)
            if teacher_session_bootstrap:
                scripts.append(teacher_session_bootstrap)
        class_detail_bootstrap = _build_class_detail_bootstrap(store, request)
        if class_detail_bootstrap:
            scripts.append(class_detail_bootstrap)
    else:
        student_auth_bootstrap = _build_student_auth_bootstrap(
            store,
            bootstrap_profile_name,
            route_key=route_key,
            request=request,
        )
        if student_auth_bootstrap:
            scripts.append(student_auth_bootstrap)
        if _normalize_route_path(route_key).startswith("/code-classroom"):
            student_session_bootstrap = _build_student_session_bootstrap(store, request, bootstrap_profile_name)
            if student_session_bootstrap:
                scripts.append(student_session_bootstrap)
    if not scripts:
        return None
    return "".join(scripts)


def _render_local_admin_login_page(request: Request) -> str:
    redirect_value = (
        _first_query_value(request, "redirect")
        or _first_query_value(request, "redirect_url")
        or _first_query_value(request, "target")
        or ""
    ).strip()
    redirect_json = json.dumps(redirect_value, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>乐启享 · 管理登录</title>
<style>
*{{box-sizing:border-box}}html,body{{height:100%;margin:0;font-family:'Segoe UI','Microsoft YaHei',sans-serif;color:#eef4ff}}
body{{display:grid;place-items:center;padding:24px;background:#07132d;overflow:hidden}}
.login-bg{{position:fixed;inset:0;width:100%;height:100%;object-fit:cover;opacity:.58;filter:saturate(1.12) contrast(1.05)}}
.login-shade{{position:fixed;inset:0;background:linear-gradient(115deg,rgba(2,8,28,.9),rgba(2,8,28,.42) 52%,rgba(2,8,28,.82)),radial-gradient(circle at 78% 25%,rgba(111,255,0,.16),transparent 34%)}}
.login-shell{{position:relative;z-index:1;display:grid;grid-template-columns:minmax(260px,430px) minmax(340px,460px);width:min(960px,100%);min-height:560px;border:1px solid rgba(255,255,255,.18);border-radius:30px;overflow:hidden;background:rgba(4,15,42,.64);box-shadow:0 35px 100px rgba(0,0,0,.48);backdrop-filter:blur(20px)}}
.brand-panel{{display:flex;flex-direction:column;justify-content:center;align-items:center;gap:26px;padding:54px;background:linear-gradient(150deg,rgba(111,255,0,.12),rgba(44,103,255,.08))}}
.brand-panel img{{width:min(230px,78%);filter:drop-shadow(0 18px 38px rgba(0,0,0,.38))}}
.brand-panel h2{{margin:0;font-size:28px;letter-spacing:.12em}}.brand-panel p{{margin:0;color:rgba(238,244,255,.72);line-height:1.8;text-align:center}}
.card{{display:flex;flex-direction:column;justify-content:center;padding:58px;background:rgba(3,12,35,.58)}}
h1{{margin:0 0 10px;font-size:32px}}.intro{{margin:0 0 28px;color:rgba(238,244,255,.68);line-height:1.7}}
label{{display:block;margin:16px 0 8px;font-size:14px;font-weight:650;color:rgba(238,244,255,.88)}}
input{{width:100%;padding:14px 16px;border:1px solid rgba(255,255,255,.18);border-radius:13px;background:rgba(255,255,255,.08);color:#fff;font-size:15px;outline:none}}
input:focus{{border-color:#6fff00;box-shadow:0 0 0 3px rgba(111,255,0,.12)}}input::placeholder{{color:rgba(238,244,255,.4)}}
button{{margin-top:22px;width:100%;padding:14px;border:0;border-radius:13px;background:#6fff00;color:#061128;font-size:16px;font-weight:800;cursor:pointer;box-shadow:0 10px 28px rgba(111,255,0,.18)}}
.hint{{margin-top:14px;font-size:12px;color:rgba(238,244,255,.48)}}.error{{margin-top:14px;color:#ff9c9c;font-size:14px;min-height:20px}}
.back{{position:fixed;z-index:2;left:24px;top:24px;color:#fff;text-decoration:none;padding:10px 16px;border:1px solid rgba(255,255,255,.25);border-radius:999px;background:rgba(3,12,35,.5);backdrop-filter:blur(12px)}}
@media(max-width:760px){{.login-shell{{grid-template-columns:1fr}}.brand-panel{{padding:34px;min-height:220px}}.brand-panel img{{width:150px}}.brand-panel p{{display:none}}.card{{padding:38px 28px}}}}
</style></head>
<body>
<video class="login-bg" autoplay loop muted playsinline poster="/_site/homepage/media/contact-bg.webp"><source src="/_site/homepage/media/signal-cloudfront-20260331-055729.mp4" type="video/mp4"></video><div class="login-shade"></div>
<a class="back" href="/">← 返回官网首页</a>
<main class="login-shell"><section class="brand-panel"><img src="/_site/homepage/media/brand-logo.png" alt="乐启享"><h2>让创造真实发生</h2><p>乐高搭建 · 机器人工程 · 少儿编程 · AI 创造</p></section>
<section class="card"><h1>欢迎回来</h1><p class="intro">登录乐启享教学管理系统</p>
<form id="local-admin-login" action="/java-api/school/tch/login" method="post">
<label for="userName">账号</label><input id="userName" name="userName" type="text" autocomplete="username" placeholder="请输入登录账号" required>
<label for="password">密码</label><input id="password" name="password" type="password" autocomplete="current-password" placeholder="请输入登录密码" required>
<input type="hidden" id="captchaVerifyParam" name="captchaVerifyParam" value=""><button type="submit">登录</button><div class="error" id="login-error"></div></form>
<div class="hint">本页面仅用于本地教学管理系统登录</div></section></main>
<script>(function(){{try{{sessionStorage.removeItem('mirror_profile');}}catch(e){{}}var form=document.getElementById('local-admin-login');var errorNode=document.getElementById('login-error');var redirectValue={redirect_json};form.addEventListener('submit',async function(event){{event.preventDefault();errorNode.textContent='';var payload={{userName:form.userName.value,password:form.password.value,captchaVerifyParam:form.captchaVerifyParam.value||''}};try{{var response=await fetch(form.action,{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify(payload),credentials:'same-origin'}});var data=await response.json();if(data&&data.success){{var target='/background/course-management/school-curriculum';if(redirectValue){{target=redirectValue.charAt(0)==='/'?'/background'+redirectValue:'/background/'+redirectValue;}}window.location.assign(target);return;}}errorNode.textContent=(((data||{{}}).error||{{}}).message)||'登录失败';}}catch(error){{errorNode.textContent='网络异常，请稍后重试';}}}});}}());</script></body></html>"""

def _inject_teacher_session_bootstrap(text: str, script: str | None) -> str:
    if not script:
        return text
    if script in text:
        return text
    if "</head>" in text:
        return text.replace("</head>", f"{script}</head>", 1)
    if "<body" in text:
        return text.replace("<body", f"{script}<body", 1)
    return f"{script}{text}"


def _json_deep_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _permission_sort_value(node: dict[str, Any]) -> float:
    user_resource = node.get("userResource")
    for value in (
        user_resource.get("sort") if isinstance(user_resource, dict) else None,
        node.get("sort"),
    ):
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _normalize_permission_tree(nodes: Any, *, sort_nodes: bool = False) -> list[dict[str, Any]]:
    if not isinstance(nodes, list):
        return []

    normalized: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue

        normalized_node = _json_deep_copy(node)
        user_resource = normalized_node.get("userResource")
        if isinstance(user_resource, dict):
            normalized_node.update(_json_deep_copy(user_resource))
        normalized_node["children"] = _normalize_permission_tree(
            normalized_node.get("children"),
            sort_nodes=sort_nodes,
        )
        normalized.append(normalized_node)

    if sort_nodes:
        normalized.sort(key=_permission_sort_value)
    return normalized


def _teacher_auth_tree_nodes(store: MirrorStore, profile_name: str = "teacher") -> list[dict[str, Any]]:
    teacher_profile = store.get_profile(profile_name) or store.get_profile("teacher") or {}
    login_content = teacher_profile.get("login_content") or {}
    auth_tree = login_content.get("authTree")

    if isinstance(auth_tree, str) and auth_tree.strip():
        try:
            auth_tree = json.loads(auth_tree)
        except Exception:
            auth_tree = None

    if isinstance(auth_tree, dict):
        normalized_auth_tree = _normalize_permission_tree(auth_tree.get("children"), sort_nodes=True)
        if normalized_auth_tree:
            return normalized_auth_tree
    return []


def _teacher_permission_tree(store: MirrorStore, profile_name: str = "teacher") -> list[dict[str, Any]]:
    profile = store.get_profile(profile_name) or store.get_profile("teacher") or {}
    return permission_tree_for_role(_profile_role(profile_name, profile))


def _curated_permission_tree(profile_role: str | None) -> list[dict[str, Any]]:
    return permission_tree_for_role(profile_role)


def _permission_tree_as_auth_tree(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    def convert(node: dict[str, Any]) -> dict[str, Any]:
        resource = {
            key: _json_deep_copy(value)
            for key, value in node.items()
            if key != "children" and value not in (None, "")
        }
        return {
            "children": [convert(child) for child in node.get("children", []) if isinstance(child, dict)],
            "userResource": resource,
        }

    return {"children": [convert(node) for node in nodes if isinstance(node, dict)]}


def _filter_core_background_permission_tree(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        key = str(node.get("alias") or node.get("permission_key") or "").strip()
        name = str(node.get("name") or "").strip()
        if key not in CORE_BACKGROUND_ALLOWED_PERMISSION_CHILDREN and name not in CORE_BACKGROUND_ALLOWED_SUBMENUS:
            continue
        allowed_children = CORE_BACKGROUND_ALLOWED_PERMISSION_CHILDREN.get(key)
        cloned = _json_deep_copy(node)
        children = cloned.get("children")
        if isinstance(children, list) and allowed_children is not None:
            kept_children: list[dict[str, Any]] = []
            for child in children:
                if not isinstance(child, dict):
                    continue
                child_key = str(child.get("alias") or child.get("permission_key") or "").strip()
                child_name = str(child.get("name") or "").strip()
                if child_key not in allowed_children and child_name not in CORE_BACKGROUND_ALLOWED_MENU_ITEMS:
                    continue
                kept_children.append(_json_deep_copy(child))
            cloned["children"] = kept_children
        filtered.append(cloned)
    return filtered


def _maybe_filter_core_background_permission_tree(
    nodes: list[dict[str, Any]],
    *,
    route_key: str | None = None,
    request: Request | None = None,
) -> list[dict[str, Any]]:
    should_filter = False
    if route_key and _is_core_background_route(route_key):
        should_filter = True
    elif request is not None and _is_core_background_request(request, route_key=route_key):
        should_filter = True
    if not should_filter:
        return nodes
    return _filter_core_background_permission_tree(nodes)


def _has_admin_permission_fields(nodes: list[dict[str, Any]]) -> bool:
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if any(key in node for key in ("permission_key", "icon_url")):
            return True
        children = node.get("children")
        if isinstance(children, list) and _has_admin_permission_fields(children):
            return True
    return False


def _load_json_body(request_body: bytes) -> dict[str, Any]:
    if not request_body:
        return {}
    try:
        payload = json.loads(request_body.decode("utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_request_payload(request_body: bytes) -> Any:
    if not request_body:
        return {}
    try:
        return json.loads(request_body.decode("utf-8"))
    except Exception:
        parsed = parse_qs(request_body.decode("utf-8", errors="ignore"), keep_blank_values=True)
        normalized: dict[str, Any] = {}
        for key, values in parsed.items():
            normalized[key] = values[0] if len(values) == 1 else values
        return normalized


def _parse_int_like(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text or not text.isdigit():
        return None
    return int(text)


def _append_student_ids(target: list[int], value: Any) -> None:
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _append_student_ids(target, item)
        return
    if isinstance(value, dict):
        for key in ("stuId", "id", "studentId", "student_user_id", "studentUserId", "userId"):
            if key in value:
                _append_student_ids(target, value[key])
                return
        return
    if isinstance(value, str):
        text = value.strip()
        if text.startswith(("[", "{")):
            try:
                _append_student_ids(target, json.loads(text))
                return
            except Exception:
                pass
        if "," in text:
            for item in text.split(","):
                _append_student_ids(target, item)
            return
        if text != value:
            _append_student_ids(target, text)
            return
    normalized = _parse_int_like(value)
    if normalized is not None and normalized not in target:
        target.append(normalized)


def _extract_student_ids(payload: Any, request: Request) -> list[int]:
    student_ids: list[int] = []
    if isinstance(payload, dict):
        for key in ("stuIds", "ids", "studentIds", "chooseStuIds", "userIds", "studentDataArr", "studentData"):
            if key in payload:
                _append_student_ids(student_ids, payload[key])
        for key in ("stuId", "id", "studentId", "student_user_id", "studentUserId", "userId"):
            if key in payload:
                _append_student_ids(student_ids, payload[key])
    elif isinstance(payload, (list, tuple, set)):
        _append_student_ids(student_ids, payload)

    for key in ("stuId", "id", "studentId", "student_user_id", "studentUserId", "userId"):
        query_value = _first_query_value(request, key)
        if query_value is not None:
            _append_student_ids(student_ids, query_value)
    return student_ids


def _append_int_values(target: list[int], value: Any) -> None:
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _append_int_values(target, item)
        return
    if isinstance(value, dict):
        for nested_value in value.values():
            _append_int_values(target, nested_value)
        return
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = None
            if parsed is not None:
                _append_int_values(target, parsed)
                return
        if "," in text:
            for item in text.split(","):
                _append_int_values(target, item)
            return
    normalized = _parse_int_like(value)
    if normalized is not None and normalized not in target:
        target.append(normalized)


def _extract_teaching_plan_ids(payload: Any, request: Request) -> list[int]:
    teaching_plan_ids: list[int] = []
    if isinstance(payload, dict):
        for key in ("tchPlanIdArr", "tchPlanIds", "teachingPlanIds", "ids"):
            if key in payload:
                _append_int_values(teaching_plan_ids, payload[key])
        for key in ("tchPlanId", "teachingPlanId", "id"):
            if key in payload:
                _append_int_values(teaching_plan_ids, payload[key])

    for key in ("tchPlanIdArr", "tchPlanIds", "teachingPlanIds", "tchPlanId", "teachingPlanId", "id"):
        query_value = _first_query_value(request, key)
        if query_value is not None:
            _append_int_values(teaching_plan_ids, query_value)
    return teaching_plan_ids


def _payload_json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if value in (None, ""):
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = None
            if isinstance(parsed, list):
                return parsed
        return [item.strip() for item in text.split(",") if item.strip()]
    return [value]


def _extract_lesson_ids(payload: Any, request: Request) -> list[int]:
    lesson_ids: list[int] = []
    if isinstance(payload, dict):
        for key in (
            "lessonIds",
            "lessonIdArr",
            "lesson_id_arr",
            "curriculumMaterialIds",
            "curriculumMaterialIdArr",
            "curriculum_meterial_ids",
            "curriculum_material_ids",
        ):
            if key in payload:
                _append_int_values(lesson_ids, payload[key])
        for key in ("lessonId", "curriculumMaterialId", "curriculum_meterial_id", "curriculum_material_id"):
            if key in payload:
                _append_int_values(lesson_ids, payload[key])

    for key in (
        "lessonIds",
        "lessonIdArr",
        "curriculumMaterialIds",
        "curriculumMaterialIdArr",
        "lessonId",
        "curriculumMaterialId",
    ):
        query_value = _first_query_value(request, key)
        if query_value is not None:
            _append_int_values(lesson_ids, query_value)
    return lesson_ids


def _plan_rows_for_class(store: MirrorStore, class_id: int | str | None) -> list[dict[str, Any]]:
    normalized_class_id = _coerce_int(class_id)
    if normalized_class_id is None:
        return []
    rows: list[dict[str, Any]] = []
    for plan in store.list_teaching_plans():
        if not isinstance(plan, dict):
            continue
        plan_class_id = _coerce_int(((plan.get("classInfo") or {}).get("id")) or plan.get("curriculum_class_id"))
        if plan_class_id == normalized_class_id:
            rows.append(plan)
    rows.sort(
        key=lambda row: (
            str(row.get("class_date") or row.get("start_class_date") or ""),
            _coerce_int(row.get("sort_num")) or 0,
            _coerce_int(row.get("id")) or 0,
        )
    )
    return rows


def _student_class_membership_rows(store: MirrorStore, student_id: int | str | None) -> list[dict[str, Any]]:
    normalized_student_id = _coerce_int(student_id)
    if normalized_student_id is None:
        return []
    rows: list[dict[str, Any]] = []
    for class_row in store.list_classes():
        if not isinstance(class_row, dict):
            continue
        class_id = _coerce_int(class_row.get("id"))
        if class_id is None:
            continue
        payload = store.get_class_student_payload(class_id) or {}
        student_rows = payload.get("studentList") if isinstance(payload, dict) else []
        if not isinstance(student_rows, list):
            continue
        found = False
        for row in student_rows:
            if not isinstance(row, dict):
                continue
            candidate_student_id = _coerce_int(row.get("student_user_id"))
            if candidate_student_id is None:
                candidate_student_id = _coerce_int(((row.get("studentInfo") or {}).get("id")))
            if candidate_student_id == normalized_student_id:
                found = True
                break
        if not found:
            continue
        rows.append(
            {
                "classId": class_id,
                "className": class_row.get("name") or "",
                "classInfo": _json_deep_copy(class_row),
            }
        )
    return rows


def _candidate_student_display_name(student_row: dict[str, Any], *, default_id: Any = None) -> str:
    student_info = student_row.get("studentUserInfo") if isinstance(student_row.get("studentUserInfo"), dict) else {}
    for source in (student_info, student_row):
        if not isinstance(source, dict):
            continue
        for key in ("realname", "realName", "stuName", "studentName", "name"):
            value = str(source.get(key) or "").strip()
            if value:
                return value
    student_id = _coerce_int(student_row.get("id") or student_row.get("student_user_id") or default_id)
    return f"Student {student_id}" if student_id is not None else "Local Mirror Student"


def _local_receipt_id_for_student(student_id: int | str | None) -> int:
    normalized_student_id = _coerce_int(student_id) or 0
    return normalized_student_id * 1000 + 1


def _build_local_receipt_info_row(
    store: MirrorStore,
    student_row: dict[str, Any],
    *,
    receipt_id: int | str | None = None,
) -> dict[str, Any]:
    student_id = (
        _coerce_int(student_row.get("id"))
        or _coerce_int(student_row.get("student_user_id"))
        or _coerce_int(student_row.get("studentUserId"))
        or 0
    )
    normalized_receipt_id = _coerce_int(receipt_id) or _local_receipt_id_for_student(student_id)
    student_info = student_row.get("studentUserInfo") if isinstance(student_row.get("studentUserInfo"), dict) else {}
    campus_id = (
        _coerce_int(student_info.get("eduCampusId"))
        or _coerce_int(student_info.get("educational_institution_campus_id"))
        or _coerce_int(student_row.get("eduCampusId"))
        or _coerce_int(student_row.get("educational_institution_campus_id"))
        or _teacher_primary_campus_id(store)
        or 0
    )
    display_name = _candidate_student_display_name(student_row, default_id=student_id)
    bill_code = f"LOCAL-RCPT-{normalized_receipt_id}"
    return {
        "id": normalized_receipt_id,
        "num": normalized_receipt_id,
        "receiptNo": normalized_receipt_id,
        "receipt_id": normalized_receipt_id,
        "student_user_id": student_id,
        "studentUserId": student_id,
        "stuId": student_id,
        "student_name": display_name,
        "studentName": display_name,
        "stuName": display_name,
        "type": "1",
        "receipt_type": 1,
        "bill_code": bill_code,
        "billCode": bill_code,
        "leader": "",
        "educational_institution_campus_id": campus_id,
        "eduCampusId": campus_id,
        "campusId": campus_id,
        "campusName": student_row.get("campusName") or _teacher_primary_campus_name(store) or "",
        "schoolName": student_row.get("schoolName") or "",
        "remark": "Local mirrored receipt",
        "charge_type": 1,
        "chargeType": 1,
        "charge_date": datetime.now().strftime("%Y-%m-%d"),
        "chargeDate": datetime.now().strftime("%Y-%m-%d"),
        "total_amount": 0,
        "totalAmount": 0,
        "other_amount": 0,
        "bullet_amount": 0,
        "discount_amount": 0,
        "final_amount": 0,
        "finalAmount": 0,
        "goods_str": "Default Goods",
        "goodsStr": "Default Goods",
        "lession_str": "Local Course",
        "lesson_str": "Local Course",
    }


def _build_local_class_goods_info_row(
    store: MirrorStore,
    student_row: dict[str, Any],
    *,
    goods_id: int | str | None = None,
    title: str | None = None,
    receipt_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    student_id = (
        _coerce_int(student_row.get("id"))
        or _coerce_int(student_row.get("student_user_id"))
        or _coerce_int(student_row.get("studentUserId"))
        or 0
    )
    normalized_goods_id = _coerce_int(goods_id) or student_id * 10 + 1
    normalized_title = (title or "Default Goods").strip() or "Default Goods"
    normalized_receipt_info = _json_deep_copy(receipt_info or _build_local_receipt_info_row(store, student_row))
    receipt_id = _coerce_int(normalized_receipt_info.get("id")) or _local_receipt_id_for_student(student_id)
    return {
        "id": normalized_goods_id,
        "receipt_id": receipt_id,
        "receiptId": receipt_id,
        "student_user_id": student_id,
        "studentUserId": student_id,
        "xm_goods_id": normalized_goods_id,
        "goods_id": normalized_goods_id,
        "goodsId": normalized_goods_id,
        "title": normalized_title,
        "name": normalized_title,
        "goods_name": normalized_title,
        "goodsName": normalized_title,
        "num": 1,
        "buy_num": 1,
        "buyNum": 1,
        "unit_price": 0,
        "unitPrice": 0,
        "total_amount": 0,
        "totalAmount": 0,
        "receiptInfo": normalized_receipt_info,
    }


def _all_candidate_student_rows(store: MirrorStore) -> list[dict[str, Any]]:
    rows_by_id: dict[int, dict[str, Any]] = {}
    for row in _build_select_study_rows(store):
        if not isinstance(row, dict):
            continue
        student_id = _coerce_int(row.get("stuId"))
        if student_id is None or student_id in rows_by_id:
            continue
        snapshot = store._student_snapshot_by_id(student_id)
        class_rows = _student_class_membership_rows(store, student_id)
        class_names = [str(class_row.get("className") or "").strip() for class_row in class_rows if class_row.get("className")]
        goods_id = student_id * 10 + 1
        candidate_row = {
            "id": student_id,
            "name": snapshot.get("name") or row.get("stuAccount") or f"student-{student_id}",
            "normal_state": _coerce_int(row.get("normalState")) or 1,
            "normalState": _coerce_int(row.get("normalState")) or 1,
            "headimg_url": snapshot.get("headimg_url") or "",
            "studentUserInfo": _json_deep_copy(snapshot.get("studentUserInfo") or {}),
            "campusName": row.get("eduCampusName") or "",
            "schoolName": row.get("schoolName") or "",
            "enddate": row.get("endDate") or "",
            "stuClassArr": class_rows,
            "class_str": " , ".join(class_names) if class_names else "--",
            "xm_goods_id": goods_id,
        }
        receipt_info = _build_local_receipt_info_row(store, candidate_row)
        class_goods_info = _build_local_class_goods_info_row(
            store,
            candidate_row,
            goods_id=goods_id,
            receipt_info=receipt_info,
        )
        candidate_row["ClassGoodsInfo"] = class_goods_info
        candidate_row["stuClassGoodsInfoArr"] = [class_goods_info]
        candidate_row["stuClassGoodsInfoList"] = [class_goods_info]
        candidate_row["xmGoodsList"] = _build_local_xm_goods_rows(candidate_row, store=store)
        rows_by_id[student_id] = candidate_row
    return sorted(
        rows_by_id.values(),
        key=lambda row: (
            str(row.get("name") or ""),
            _coerce_int(row.get("id")) or 0,
        ),
    )


def _candidate_student_row_by_id(store: MirrorStore, student_id: int | str | None) -> dict[str, Any] | None:
    normalized_student_id = _coerce_int(student_id)
    if normalized_student_id is None:
        return None
    for row in _all_candidate_student_rows(store):
        if _coerce_int((row or {}).get("id")) == normalized_student_id:
            return row
    return None


def _build_local_xm_goods_rows(student_row: dict[str, Any], *, store: MirrorStore | None = None) -> list[dict[str, Any]]:
    student_id = _coerce_int(student_row.get("id")) or 0
    goods_rows: list[dict[str, Any]] = []
    class_goods_info = student_row.get("ClassGoodsInfo") if isinstance(student_row.get("ClassGoodsInfo"), dict) else {}
    class_receipt_info = class_goods_info.get("receiptInfo") if isinstance(class_goods_info.get("receiptInfo"), dict) else None
    receipt_info = _json_deep_copy(class_receipt_info or {})
    if not receipt_info:
        receipt_info = (
            _build_local_receipt_info_row(store, student_row)
            if store is not None
            else {
                "id": _local_receipt_id_for_student(student_id),
                "student_user_id": student_id,
                "studentUserId": student_id,
            }
        )
    for goods in student_row.get("xmGoodsList") or []:
        if not isinstance(goods, dict):
            continue
        normalized = _json_deep_copy(goods)
        goods_id = _coerce_int(normalized.get("id")) or student_id * 10 + len(goods_rows) + 1
        title = str(normalized.get("title") or normalized.get("name") or f"Goods {goods_id}").strip()
        normalized["id"] = goods_id
        normalized["title"] = title
        normalized["name"] = title
        normalized["goods_name"] = title
        normalized["student_user_id"] = student_id
        if receipt_info:
            normalized["receipt_id"] = _coerce_int(receipt_info.get("id")) or _local_receipt_id_for_student(student_id)
            normalized["receiptInfo"] = _json_deep_copy(receipt_info)
        goods_rows.append(normalized)
    if goods_rows:
        return goods_rows
    default_goods_id = student_id * 10 + 1
    if not receipt_info:
        receipt_info = _json_deep_copy(class_receipt_info or {})
    return [
        {
            "id": default_goods_id,
            "title": "Default Goods",
            "name": "Default Goods",
            "goods_name": "Default Goods",
            "student_user_id": student_id,
            "receipt_id": _coerce_int(receipt_info.get("id")) or _local_receipt_id_for_student(student_id),
            "receiptInfo": _json_deep_copy(receipt_info) if receipt_info else {},
        }
    ]


def _build_local_xm_account_row(store: MirrorStore, student_row: dict[str, Any]) -> dict[str, Any]:
    student_id = _coerce_int(student_row.get("id")) or 0
    student_info = student_row.get("studentUserInfo") if isinstance(student_row.get("studentUserInfo"), dict) else {}
    display_name = str(
        student_info.get("realname")
        or student_row.get("realname")
        or student_row.get("stuName")
        or student_row.get("name")
        or f"Student {student_id}"
    ).strip()
    campus_id = _coerce_int(student_info.get("eduCampusId") or student_row.get("eduCampusId") or _teacher_primary_campus_id(store)) or 0
    account_no = f"XM{student_id:06d}"
    return {
        "id": student_id * 100 + 1,
        "accountNo": account_no,
        "account_no": account_no,
        "stuNames": display_name,
        "stuName": display_name,
        "student_user_id": student_id,
        "studentUserId": student_id,
        "userId": student_id,
        "eduCampusId": campus_id,
        "campusName": student_row.get("campusName") or _teacher_primary_campus_name(store) or "",
        "schoolName": student_row.get("schoolName") or "",
        "amount": 0,
        "giveAmount": 0,
        "historyAmount": 0,
        "historyGiveAmount": 0,
        "usableAmount": 0,
        "classStr": student_row.get("class_str") or "--",
        "xmGoodsList": _build_local_xm_goods_rows(student_row, store=store),
    }


def _candidate_student_row_by_receipt_id(store: MirrorStore, receipt_id: int | str | None) -> dict[str, Any] | None:
    normalized_receipt_id = _coerce_int(receipt_id)
    if normalized_receipt_id is None:
        return None
    for row in _all_candidate_student_rows(store):
        if not isinstance(row, dict):
            continue
        class_goods_rows: list[dict[str, Any]] = []
        class_goods_info = row.get("ClassGoodsInfo")
        if isinstance(class_goods_info, dict):
            class_goods_rows.append(class_goods_info)
        for item in row.get("stuClassGoodsInfoArr") or []:
            if isinstance(item, dict):
                class_goods_rows.append(item)
        for goods_row in class_goods_rows:
            if _coerce_int(goods_row.get("receipt_id") or goods_row.get("receiptId")) == normalized_receipt_id:
                return row
            receipt_info = goods_row.get("receiptInfo")
            if isinstance(receipt_info, dict) and _coerce_int(receipt_info.get("id") or receipt_info.get("receipt_id")) == normalized_receipt_id:
                return row
    return None


def _student_row_for_local_receipt(store: MirrorStore, receipt_id: int | str | None) -> dict[str, Any]:
    normalized_receipt_id = _coerce_int(receipt_id)
    matched_row = _candidate_student_row_by_receipt_id(store, normalized_receipt_id)
    if matched_row is not None:
        return matched_row
    inferred_student_id = (normalized_receipt_id - 1) // 1000 if normalized_receipt_id and normalized_receipt_id > 1 else 0
    matched_row = _candidate_student_row_by_id(store, inferred_student_id)
    if matched_row is not None:
        return matched_row
    return {
        "id": inferred_student_id,
        "name": f"Student {inferred_student_id}" if inferred_student_id else "Local Mirror Student",
        "studentUserInfo": {},
        "campusName": _teacher_primary_campus_name(store) or "",
        "schoolName": "",
    }


def _build_local_receipt_charge_goods_rows(store: MirrorStore, receipt_id: int | str | None) -> list[dict[str, Any]]:
    normalized_receipt_id = _coerce_int(receipt_id)
    student_row = _student_row_for_local_receipt(store, normalized_receipt_id)
    student_id = _coerce_int(student_row.get("id")) or 0
    class_goods_info = student_row.get("ClassGoodsInfo") if isinstance(student_row.get("ClassGoodsInfo"), dict) else {}
    class_receipt_info = class_goods_info.get("receiptInfo") if isinstance(class_goods_info.get("receiptInfo"), dict) else None
    receipt_info = _json_deep_copy(class_receipt_info or _build_local_receipt_info_row(store, student_row, receipt_id=normalized_receipt_id))
    if normalized_receipt_id is not None:
        receipt_info["id"] = normalized_receipt_id
        receipt_info["receipt_id"] = normalized_receipt_id
    receipt_id_value = _coerce_int(receipt_info.get("id")) or _local_receipt_id_for_student(student_id)
    goods_id = (
        _coerce_int(class_goods_info.get("id"))
        or _coerce_int(class_goods_info.get("goods_id"))
        or _coerce_int(class_goods_info.get("goodsId"))
        or student_id * 10 + 1
    )
    goods_name = str(
        class_goods_info.get("goods_name")
        or class_goods_info.get("goodsName")
        or class_goods_info.get("title")
        or class_goods_info.get("name")
        or "Default Goods"
    ).strip() or "Default Goods"
    return [
        {
            "id": goods_id,
            "receipt_id": receipt_id_value,
            "receiptId": receipt_id_value,
            "student_user_id": student_id,
            "studentUserId": student_id,
            "type": "2",
            "curriculum_id": 0,
            "curriculumId": 0,
            "class_id": 0,
            "classId": 0,
            "goods_id": goods_id,
            "goodsId": goods_id,
            "xm_goods_id": goods_id,
            "title": goods_name,
            "name": goods_name,
            "goods_name": goods_name,
            "goodsName": goods_name,
            "goods_str": goods_name,
            "goodsStr": goods_name,
            "lession_str": "Local Course",
            "lesson_str": "Local Course",
            "unit": "item",
            "num": 1,
            "buy_num": 1,
            "buyNum": 1,
            "refund_num": 1,
            "refundNum": 1,
            "original_unit_price": 0,
            "originalUnitPrice": 0,
            "now_unit_price": 0,
            "nowUnitPrice": 0,
            "unit_price": 0,
            "unitPrice": 0,
            "discount": 100,
            "give_num": 0,
            "giveNum": 0,
            "total_amount": 0,
            "totalAmount": 0,
            "curriculumInfo": {
                "id": 0,
                "title": "Local Course",
                "name": "Local Course",
                "subjectName": "",
            },
            "goodsInfo": {
                "id": goods_id,
                "name": goods_name,
                "title": goods_name,
                "unit": "item",
            },
            "receiptInfo": receipt_info,
        }
    ]


def _build_local_receipt_account_rows(store: MirrorStore, receipt_id: int | str | None) -> list[dict[str, Any]]:
    normalized_receipt_id = _coerce_int(receipt_id)
    student_row = _student_row_for_local_receipt(store, normalized_receipt_id)
    receipt_info = _build_local_receipt_info_row(store, student_row, receipt_id=normalized_receipt_id)
    receipt_id_value = _coerce_int(receipt_info.get("id")) or 0
    amount = _coerce_int(receipt_info.get("final_amount") or receipt_info.get("total_amount")) or 0
    return [
        {
            "id": receipt_id_value * 10 + 1,
            "receipt_id": receipt_id_value,
            "receiptId": receipt_id_value,
            "accountName": "Local Account",
            "account_name": "Local Account",
            "name": "Local Account",
            "amount": amount,
            "pay_amount": amount,
            "payAmount": amount,
            "remark": "Local mirrored receipt account",
        }
    ]


def _build_student_candidate_rows_for_class(
    store: MirrorStore,
    request: Request,
    *,
    class_id: int | str | None,
    include_existing: bool,
    include_xm_goods: bool,
) -> list[dict[str, Any]]:
    normalized_class_id = _coerce_int(class_id)
    existing_student_ids: set[int] = set()
    if normalized_class_id is not None:
        payload = store.get_class_student_payload(normalized_class_id) or {}
        student_rows = payload.get("studentList") if isinstance(payload, dict) else []
        if not isinstance(student_rows, list):
            student_rows = []
        for row in student_rows:
            if not isinstance(row, dict):
                continue
            student_id = _coerce_int(row.get("student_user_id")) or _coerce_int(((row.get("studentInfo") or {}).get("id")))
            if student_id is not None:
                existing_student_ids.add(student_id)

    account_filter = (_first_query_value(request, "name") or "").strip().lower()
    realname_filter = (_first_query_value(request, "realname") or _first_query_value(request, "realName") or "").strip().lower()
    rows: list[dict[str, Any]] = []
    for row in _all_candidate_student_rows(store):
        student_id = _coerce_int(row.get("id"))
        if student_id is None:
            continue
        if not include_existing and student_id in existing_student_ids:
            continue
        candidate_account = str(row.get("name") or "").strip().lower()
        candidate_realname = str(((row.get("studentUserInfo") or {}).get("realname")) or "").strip().lower()
        if account_filter and account_filter not in candidate_account:
            continue
        if realname_filter and realname_filter not in candidate_realname:
            continue
        normalized = _json_deep_copy(row)
        if not include_xm_goods:
            normalized["xmGoodsList"] = normalized.get("xmGoodsList") or []
        rows.append(normalized)
    return rows


def _build_no_divide_student_candidate_rows_for_class(
    store: MirrorStore,
    request: Request,
    *,
    class_id: int | str | None,
) -> list[dict[str, Any]]:
    rows = _build_student_candidate_rows_for_class(
        store,
        request,
        class_id=class_id,
        include_existing=False,
        include_xm_goods=True,
    )
    filtered_rows: list[dict[str, Any]] = []
    for row in rows:
        class_rows = row.get("stuClassArr")
        if isinstance(class_rows, list) and class_rows:
            continue
        class_text = str(row.get("class_str") or row.get("classStr") or "").strip()
        if class_text and class_text != "--":
            continue
        filtered_rows.append(row)
    return filtered_rows


def _build_student_candidate_rows_for_teaching_plan(
    store: MirrorStore,
    request: Request,
    *,
    teaching_plan_id: int | str | None,
    include_xm_goods: bool,
) -> list[dict[str, Any]]:
    normalized_teaching_plan_id = _coerce_int(teaching_plan_id)
    if normalized_teaching_plan_id is None:
        return []
    plan = _find_teaching_plan(store, normalized_teaching_plan_id) or {}
    class_id = _coerce_int(((plan.get("classInfo") or {}).get("id")) or plan.get("curriculum_class_id"))
    class_student_ids: set[int] = set()
    if class_id is not None:
        class_payload = store.get_class_student_payload(class_id) or {}
        class_student_rows = class_payload.get("studentList") if isinstance(class_payload, dict) else []
        if not isinstance(class_student_rows, list):
            class_student_rows = []
        for row in class_student_rows:
            if not isinstance(row, dict):
                continue
            student_id = _coerce_int(row.get("student_user_id")) or _coerce_int(((row.get("studentInfo") or {}).get("id")))
            if student_id is not None:
                class_student_ids.add(student_id)

    existing_plan_student_ids: set[int] = set()
    if store.is_teaching_plan_student_overridden(normalized_teaching_plan_id):
        for row in store.list_local_teaching_plan_students(normalized_teaching_plan_id):
            if not isinstance(row, dict):
                continue
            student_id = _coerce_int(row.get("student_user_id"))
            if student_id is not None:
                existing_plan_student_ids.add(student_id)

    account_filter = (_first_query_value(request, "name") or "").strip().lower()
    realname_filter = (_first_query_value(request, "realname") or _first_query_value(request, "realName") or "").strip().lower()
    rows: list[dict[str, Any]] = []
    for row in _all_candidate_student_rows(store):
        student_id = _coerce_int(row.get("id"))
        if student_id is None:
            continue
        if class_student_ids and student_id not in class_student_ids:
            continue
        if existing_plan_student_ids and student_id in existing_plan_student_ids:
            continue
        candidate_account = str(row.get("name") or "").strip().lower()
        candidate_realname = str(((row.get("studentUserInfo") or {}).get("realname")) or "").strip().lower()
        if account_filter and account_filter not in candidate_account:
            continue
        if realname_filter and realname_filter not in candidate_realname:
            continue
        normalized = _json_deep_copy(row)
        if not include_xm_goods:
            normalized["xmGoodsList"] = normalized.get("xmGoodsList") or []
        rows.append(normalized)
    return rows


def _next_class_schedule_strings(
    class_row: dict[str, Any] | None,
    existing_plans: list[dict[str, Any]],
    sequence_index: int,
) -> tuple[str, str, str]:
    reference_date: datetime | None = None
    for plan in reversed(existing_plans):
        plan_date_text = str(plan.get("class_date") or plan.get("start_class_date") or "").strip()[:10]
        if not plan_date_text:
            continue
        try:
            reference_date = datetime.strptime(plan_date_text, "%Y-%m-%d")
        except ValueError:
            continue
        break
    if reference_date is None:
        reference_date = datetime.now()
    weekdays = [
        weekday
        for weekday in (_coerce_int(item) for item in ((class_row or {}).get("week_json") or []))
        if weekday in {1, 2, 3, 4, 5, 6, 7}
    ]
    target_weekday = weekdays[0] if weekdays else reference_date.isoweekday()
    candidate = reference_date + timedelta(days=1)
    while candidate.isoweekday() != target_weekday:
        candidate += timedelta(days=1)
    candidate += timedelta(days=7 * max(sequence_index, 0))
    time_str = str((class_row or {}).get("time_str") or "").strip()
    start_time_text = "18:30"
    end_time_text = "20:00"
    if "-" in time_str:
        parts = [part.strip() for part in time_str.split("-", 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            start_time_text, end_time_text = parts
    class_date = candidate.strftime("%Y-%m-%d")
    return class_date, f"{class_date} {start_time_text}:00", f"{class_date} {end_time_text}:00"


def _build_lesson_candidate_rows_for_class(
    store: MirrorStore,
    request: Request,
    *,
    class_id: int | str | None,
) -> list[dict[str, Any]]:
    normalized_class_id = _coerce_int(class_id)
    class_row = store.find_class(normalized_class_id) or {} if normalized_class_id is not None else {}
    existing_material_ids: set[int] = set()
    if normalized_class_id is not None:
        existing_material_ids = {
            material_id
            for material_id in (
                _coerce_int(plan.get("curriculum_meterial_id")) or _coerce_int(plan.get("curriculum_material_id"))
                for plan in _plan_rows_for_class(store, normalized_class_id)
                if isinstance(plan, dict)
            )
            if material_id is not None
        }

    curriculum_id_filter = {
        curriculum_id
        for curriculum_id in (
            _coerce_int(value)
            for value in (class_row.get("curriculumIdList") or class_row.get("curriculum_id_list") or [])
        )
        if curriculum_id is not None
    }
    requested_curriculum_ids = _extract_request_int_set(
        request,
        None,
        "curriculum_id",
        "curriculumId",
        "curriculumIds",
        "curriculumIdArr",
    )
    if requested_curriculum_ids:
        curriculum_id_filter = requested_curriculum_ids if not curriculum_id_filter else curriculum_id_filter & requested_curriculum_ids

    subject_id_filter = {
        subject_id
        for subject_id in (
            _coerce_int(value)
            for value in (class_row.get("subjectIdList") or class_row.get("subject_id_list") or [])
        )
        if subject_id is not None
    }
    requested_subject_ids = _extract_request_int_set(
        request,
        None,
        "subject_id",
        "subject_ids",
        "subjectId",
        "subjectIds",
    )
    if requested_subject_ids:
        subject_id_filter = requested_subject_ids if not subject_id_filter else subject_id_filter & requested_subject_ids

    title_filter = (
        _first_query_value(request, "lesson_title")
        or _first_query_value(request, "title")
        or _first_query_value(request, "lessonTitle")
        or ""
    ).strip().lower()
    curriculum_info_map = store._curriculum_info_map()
    subject_name_map = _teacher_subject_name_map(store)

    rows: list[dict[str, Any]] = []
    for material in store.list_curriculum_materials():
        if not isinstance(material, dict):
            continue
        material_id = _coerce_int(material.get("id"))
        if material_id is None or material_id in existing_material_ids:
            continue
        material_curriculum_id = _coerce_int(material.get("curriculum_id"))
        material_subject_id = _coerce_int(material.get("subject_id"))
        if curriculum_id_filter and material_curriculum_id not in curriculum_id_filter:
            continue
        if subject_id_filter and material_subject_id not in subject_id_filter:
            continue
        material_title = str(material.get("title") or "").strip()
        if title_filter and title_filter not in material_title.lower():
            continue
        curriculum_title = str(material.get("curriculum_title") or material.get("curriculumTitle") or "").strip()
        if not curriculum_title and material_curriculum_id is not None:
            curriculum_info = store._curriculum_info_map().get(material_curriculum_id) or {}
            curriculum_title = str(curriculum_info.get("title") or curriculum_info.get("name") or "").strip()
        subject_title = str(material.get("subject_title") or material.get("subjectTitle") or "").strip()
        if not subject_title and material_subject_id is not None:
            subject_title = str(subject_name_map.get(material_subject_id) or "").strip()
        rows.append(
            {
                "id": material_id,
                "lessonId": material_id,
                "curriculumMaterialId": material_id,
                "title": material_title,
                "lesson_title": material_title,
                "lessonTitle": material_title,
                "img_url": material.get("img_url") or "",
                "ppt_url": material.get("ppt_url") or "",
                "video_url": material.get("video_url") or "",
                "subject_id": material_subject_id or 0,
                "subject_title": subject_title,
                "subjectTitle": subject_title,
                "curriculum_id": material_curriculum_id or 0,
                "curriculum_title": curriculum_title,
                "curriculumTitle": curriculum_title,
                "sort_num": _coerce_int(material.get("sort_num")) or 0,
            }
        )
    rows.sort(key=lambda row: (_coerce_int(row.get("sort_num")) or 0, _coerce_int(row.get("id")) or 0))
    return rows


def _extract_student_overlay_updates(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    updates: dict[str, Any] = {}
    for field_name, aliases in STUDENT_OVERLAY_FIELD_ALIASES.items():
        for alias in aliases:
            if alias in payload:
                updates[field_name] = payload[alias]
                break
    return updates


def _sample_qr_bytes(store: MirrorStore) -> bytes:
    for root_name in ("external", "origin"):
        root = store.root / root_name
        if not root.exists():
            continue
        for pattern in ("*.jpg", "*.jpeg", "*.png"):
            match = next(root.rglob(pattern), None)
            if match is None or not match.is_file():
                continue
            try:
                return match.read_bytes()
            except OSError:
                continue
    return b"\xff\xd8\xff\xd9"


def _student_row_id(row: dict[str, Any]) -> int | None:
    for key in ("stuId", "id", "studentId", "userId"):
        if key not in row:
            continue
        normalized = _parse_int_like(row.get(key))
        if normalized is not None:
            return normalized
    return None


def _student_overlay_is_hidden(overlay: dict[str, Any] | None) -> bool:
    if not overlay:
        return False
    return bool(overlay.get("deleted")) or bool(overlay.get("quit"))


def _student_overlay_is_historical(overlay: dict[str, Any] | None) -> bool:
    if not overlay:
        return False
    return bool(overlay.get("quit")) and not bool(overlay.get("deleted"))


def _format_total_like(original: Any, total: int) -> Any:
    if isinstance(original, str):
        return str(total)
    return total


def _apply_student_overlay_to_row(row: dict[str, Any], overlay: dict[str, Any] | None) -> dict[str, Any]:
    if not overlay:
        return row

    updated = dict(row)
    normal_state = overlay.get("normal_state")
    if normal_state not in (None, ""):
        updated["normal_state"] = normal_state
        updated["normalState"] = int(str(normal_state)) if str(normal_state).isdigit() else normal_state

    end_date = overlay.get("end_date")
    if end_date not in (None, ""):
        updated["endDate"] = end_date
        updated["end_date"] = end_date
        updated["studyDate"] = end_date
        updated["study_date"] = end_date
        updated["enddate"] = f"{end_date} 23:59:59" if len(str(end_date)) == 10 else str(end_date)

    for field_name, aliases in STUDENT_OVERLAY_FIELD_ALIASES.items():
        if field_name in {
            "normal_state",
            "end_date",
            "wechat_bound",
            "parent_wechat",
            "wcm_flag",
            "open_id",
            "authorizer_openid",
        }:
            continue
        value = overlay.get(field_name)
        if value is None:
            continue
        updated[field_name] = value
        for alias in aliases:
            updated[alias] = value

    bound_flag = overlay.get("wechat_bound")
    if bound_flag == 0:
        updated["openId"] = None
        updated["open_id"] = None
        updated["authorizerOpenid"] = None
        updated["authorizer_openid"] = None
        updated["parentWeChat"] = overlay.get("parent_wechat") or DEFAULT_UNBOUND_TEXT
        updated["parent_wechat"] = updated["parentWeChat"]
        updated["wcmFlag"] = overlay.get("wcm_flag") or DEFAULT_UNBOUND_TEXT
        updated["wcm_flag"] = updated["wcmFlag"]
    elif bound_flag == 1:
        open_id = overlay.get("open_id") or updated.get("openId") or f"mirror-openid-{overlay['stu_id']}"
        updated["openId"] = open_id
        updated["open_id"] = open_id
        authorizer_openid = overlay.get("authorizer_openid")
        if authorizer_openid not in (None, ""):
            updated["authorizerOpenid"] = authorizer_openid
            updated["authorizer_openid"] = authorizer_openid
        updated["parentWeChat"] = overlay.get("parent_wechat") or updated.get("parentWeChat") or DEFAULT_BOUND_TEXT
        updated["parent_wechat"] = updated["parentWeChat"]
        updated["wcmFlag"] = overlay.get("wcm_flag") or updated.get("wcmFlag") or DEFAULT_BOUND_TEXT
        updated["wcm_flag"] = updated["wcmFlag"]
    else:
        if overlay.get("open_id") not in (None, ""):
            updated["openId"] = overlay["open_id"]
            updated["open_id"] = overlay["open_id"]
        if overlay.get("authorizer_openid") not in (None, ""):
            updated["authorizerOpenid"] = overlay["authorizer_openid"]
            updated["authorizer_openid"] = overlay["authorizer_openid"]
        if overlay.get("parent_wechat") not in (None, ""):
            updated["parentWeChat"] = overlay["parent_wechat"]
            updated["parent_wechat"] = overlay["parent_wechat"]
        if overlay.get("wcm_flag") not in (None, ""):
            updated["wcmFlag"] = overlay["wcm_flag"]
            updated["wcm_flag"] = overlay["wcm_flag"]

    if overlay.get("last_password_reset_at") not in (None, ""):
        updated["lastPasswordResetAt"] = overlay["last_password_reset_at"]
        updated["last_password_reset_at"] = overlay["last_password_reset_at"]

    return updated


def _build_local_student_auth_content(stu_id: int, overlay: dict[str, Any] | None) -> dict[str, Any]:
    content = {
        "id": stu_id,
        "stuId": stu_id,
        "normalState": 1,
        "normal_state": "1",
        "zoneAuth": 0,
        "zone_auth": 0,
        "testAuth": 0,
        "test_auth": 0,
        "ojAuth": 0,
        "oj_auth": 0,
        "ojAnalysisAuth": 0,
        "oj_analysis_auth": 0,
        "ojTestcaseAuth": 0,
        "oj_testcase_auth": 0,
        "stuNoteAuth": 0,
        "stu_note_auth": 0,
        "pAuth": 0,
        "p_auth": 0,
    }
    return _apply_student_overlay_to_row(content, overlay)


def _build_admin_permission_tree(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def convert(node: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(node, dict):
            return None

        name = str(node.get("name") or "").strip()
        permission_key = str(node.get("permission_key") or node.get("alias") or "").strip()
        if not name and not permission_key:
            return None

        converted_children: list[dict[str, Any]] = []
        children = node.get("children")
        if isinstance(children, list):
            for child in children:
                converted_child = convert(child)
                if converted_child is not None:
                    converted_children.append(converted_child)

        converted: dict[str, Any] = {
            "name": name or permission_key,
            "children": converted_children,
        }
        if permission_key:
            converted["permission_key"] = permission_key

        icon_url = node.get("icon_url") or node.get("iconUrl")
        if icon_url not in (None, ""):
            converted["icon_url"] = icon_url

        view_scope = node.get("viewScope")
        if view_scope in (None, ""):
            view_scope = node.get("view_scope")
        if view_scope in (None, ""):
            view_scope = node.get("viewscope")
        if view_scope not in (None, ""):
            converted["viewScope"] = view_scope

        for key in ("id", "type", "level", "path", "sort", "parentId"):
            value = node.get(key)
            if value not in (None, ""):
                converted[key] = value
        return converted

    normalized_nodes = _normalize_permission_tree(nodes, sort_nodes=True)
    built: list[dict[str, Any]] = []
    for node in normalized_nodes:
        converted = convert(node)
        if converted is not None:
            built.append(converted)
    return built


def _teacher_admin_permissions(store: MirrorStore, profile_name: str = "teacher") -> list[Any]:
    return _build_admin_permission_tree(_teacher_permission_tree(store, profile_name))


def _teacher_admin_user_id(store: MirrorStore, profile_name: str = "teacher") -> Any:
    teacher_profile = store.get_profile(profile_name) or store.get_profile("teacher") or {}
    user_state = (teacher_profile.get("vuex_state") or {}).get("user") or {}
    user_info = (teacher_profile.get("fresh_auth") or {}).get("userInfo") or {}
    for value in (
        user_state.get("adminUserId"),
        user_state.get("userId"),
        user_info.get("userId"),
        user_info.get("id"),
    ):
        if value not in (None, ""):
            return value
    return None


def _minimal_local_teacher_permission_tree() -> list[dict[str, Any]]:
    return [
        {
            "alias": "tchCenter",
            "name": "教务中心",
            "sort": 5,
            "children": [
                {
                    "alias": "students-management1",
                    "name": "学员管理",
                    "sort": 1,
                    "children": [{"alias": "currentStudent", "name": "在读学员", "sort": 1, "children": []}],
                },
                {
                    "alias": "class-management1",
                    "name": "班级管理",
                    "sort": 2,
                    "children": [{"alias": "inClass", "name": "在读班级", "sort": 1, "children": []}],
                },
                {
                    "alias": "teachplan1",
                    "name": "教学计划",
                    "sort": 4,
                    "children": [{"alias": "courseScheduled", "name": "已排课", "sort": 1, "children": []}],
                },
            ],
        },
        {
            "alias": "courseCenter",
            "name": "课程中心",
            "sort": 6,
            "children": [
                {
                    "alias": "course-list",
                    "name": "课程管理",
                    "sort": 1,
                    "children": [
                        {"alias": "courseQuery", "name": "查询", "sort": 1, "children": []},
                        {"alias": "school-curriculum", "name": "课程体系", "sort": 2, "children": []},
                    ],
                }
            ],
        },
    ]


def _local_staff_role_rows() -> list[dict[str, Any]]:
    return [
        {
            "id": 1,
            "roleId": 1,
            "name": "机构老师",
            "roleName": "机构老师",
            "tchState": True,
            "platformTch": True,
            "eduTch": True,
            "state": 1,
        },
        {
            "id": 2,
            "roleId": 2,
            "name": "教务管理员",
            "roleName": "教务管理员",
            "tchState": True,
            "platformTch": True,
            "eduTch": True,
            "state": 1,
        },
    ]


def _profile_user_id_from_profile(profile: dict[str, Any] | None) -> int | None:
    if not isinstance(profile, dict):
        return None
    user_state = (profile.get("vuex_state") or {}).get("user") or {}
    user_state_info = user_state.get("userInfo") if isinstance(user_state.get("userInfo"), dict) else {}
    user_info = (profile.get("fresh_auth") or {}).get("userInfo") or {}
    for value in (
        user_state.get("adminUserId"),
        user_state.get("userId"),
        user_info.get("userId"),
        user_info.get("id"),
        user_state_info.get("userId"),
        user_state_info.get("id"),
    ):
        normalized = _coerce_int(value)
        if normalized is not None:
            return normalized
    return None


def _local_staff_profiles(store: MirrorStore, *, include_admin: bool = True) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for profile in store.list_profiles(login_path=TEACHER_LOGIN_PATH):
        profile_name = str(profile.get("profile_name") or "").strip()
        profile_role = _profile_role(profile_name, profile)
        if not _is_teacher_like_role(profile_role):
            continue
        if profile_role == "admin" and not include_admin:
            continue
        rows.append(profile)
    return sorted(
        rows,
        key=lambda profile: (
            0 if _profile_role(profile.get("profile_name"), profile) == "admin" else 1,
            _profile_user_id_from_profile(profile) or 0,
            str(profile.get("username") or ""),
        ),
    )


def _staff_role_ids(profile_name: str, profile: dict[str, Any], user_info: dict[str, Any]) -> list[int]:
    role_ids = _extract_int_list(user_info.get("eduRoleIdList"))
    if not role_ids:
        role_ids = _extract_int_list(user_info.get("roleIdList"))
    if not role_ids:
        role_list = (profile.get("fresh_auth") or {}).get("roleList")
        if isinstance(role_list, list):
            for role_row in role_list:
                if not isinstance(role_row, dict):
                    continue
                _append_unique_int(role_ids, role_row.get("id") or role_row.get("roleId"))
    if not role_ids:
        role_ids = [2] if _profile_role(profile_name, profile) == "admin" else [1]
    return role_ids


def _default_staff_subject_curriculum_rows(store: MirrorStore) -> list[dict[str, Any]]:
    grouped_rows: dict[int, dict[str, Any]] = {}
    for subject in _teacher_subject_catalog(store):
        subject_id = _coerce_int(subject.get("id"))
        if subject_id is None:
            continue
        grouped_rows[subject_id] = {
            "subjectId": subject_id,
            "subject_id": subject_id,
            "name": subject.get("name") or "",
            "subjectName": subject.get("name") or "",
            "curriculumIdList": [],
            "curriculumList": [],
        }

    for curriculum in _build_teacher_curriculum_rows(store, _synthetic_request()):
        if not isinstance(curriculum, dict):
            continue
        subject_id = _coerce_int(curriculum.get("subject_id"))
        curriculum_id = _coerce_int(curriculum.get("id"))
        if subject_id is None or curriculum_id is None:
            continue
        row = grouped_rows.setdefault(
            subject_id,
            {
                "subjectId": subject_id,
                "subject_id": subject_id,
                "name": curriculum.get("subjectName") or "",
                "subjectName": curriculum.get("subjectName") or "",
                "curriculumIdList": [],
                "curriculumList": [],
            },
        )
        if curriculum_id not in row["curriculumIdList"]:
            row["curriculumIdList"].append(curriculum_id)
            row["curriculumList"].append(
                {
                    "id": curriculum_id,
                    "curriculumId": curriculum_id,
                    "title": curriculum.get("title") or "",
                    "subjectId": subject_id,
                    "subject_id": subject_id,
                    "subjectName": curriculum.get("subjectName") or row.get("subjectName") or "",
                    "subject_name": curriculum.get("subject_name") or row.get("subjectName") or "",
                }
            )

    return sorted(grouped_rows.values(), key=lambda row: (_coerce_int(row.get("subjectId")) or 0, row.get("name") or ""))


def _staff_subject_curriculum_rows(store: MirrorStore, profile_name: str, user_info: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("subjectCurriculumDtoList", "subjectCurriculumList"):
        rows = user_info.get(key)
        if isinstance(rows, list) and rows:
            return _json_deep_copy(rows)
    return _default_staff_subject_curriculum_rows(store)


def _staff_account_row(
    store: MirrorStore,
    profile: dict[str, Any],
    *,
    include_subjects: bool = False,
) -> dict[str, Any]:
    profile_name = str(profile.get("profile_name") or "").strip()
    user_info = _hydrate_teacher_user_info(store, _teacher_user_info(store, profile_name), profile_name)
    school_info = _hydrate_teacher_school_info(store, _teacher_school_info(store, profile_name), profile_name)
    user_id = _profile_user_id_from_profile(profile) or 0
    username = str(profile.get("username") or user_info.get("name") or f"teacher{user_id or 1}").strip()
    real_name = str(user_info.get("realName") or user_info.get("realname") or username).strip()
    campus_ids = _extract_campus_ids(user_info.get("eduCampusIdList"))
    if not campus_ids:
        campus_ids = _teacher_selected_school_ids(store, profile_name)
    if not campus_ids:
        campus_ids = _extract_campus_ids(user_info.get("eduCampusId") or school_info.get("eduCampusId"))
    role_ids = _staff_role_ids(profile_name, profile, user_info)
    role_map = {
        _coerce_int(role_row.get("id")) or _coerce_int(role_row.get("roleId")) or 0: role_row
        for role_row in _local_staff_role_rows()
    }
    role_names = [
        str((role_map.get(role_id) or {}).get("roleName") or (role_map.get(role_id) or {}).get("name") or role_id)
        for role_id in role_ids
    ]
    campus_rows = _build_user_campus_rows(store, profile_name)
    first_campus_name = str(
        (campus_rows[0].get("campusName") if campus_rows else "")
        or school_info.get("campusName")
        or school_info.get("name")
        or ""
    ).strip()
    subject_rows = _staff_subject_curriculum_rows(store, profile_name, user_info) if include_subjects else []

    row = {
        "id": user_id,
        "userId": user_id,
        "teacherId": user_id,
        "tchId": user_id,
        "name": username,
        "username": username,
        "userName": username,
        "realName": real_name,
        "realname": real_name,
        "nickName": str(user_info.get("nickName") or user_info.get("nick_name") or "").strip(),
        "sex": user_info.get("sex") or "",
        "phoneNum": str(user_info.get("phoneNum") or "").strip(),
        "userImageUrl": user_info.get("userImageUrl") or user_info.get("headimgUrl") or DEFAULT_HOMEPAGE_AVATAR_URL,
        "headimgUrl": user_info.get("headimgUrl") or user_info.get("userImageUrl") or DEFAULT_HOMEPAGE_AVATAR_URL,
        "state": str(user_info.get("state") or "在职"),
        "isFullOrPart": str(user_info.get("isFullOrPart") or ""),
        "eduCampusId": campus_ids[0] if campus_ids else (_coerce_int(school_info.get("eduCampusId")) or 0),
        "eduCampusIdList": _json_deep_copy(campus_ids),
        "eduCampusName": first_campus_name,
        "campusName": first_campus_name,
        "eduCampusDtoList": _json_deep_copy(campus_rows),
        "eduRoleIdList": _json_deep_copy(role_ids),
        "roleIdList": _json_deep_copy(role_ids),
        "roleNameList": _json_deep_copy(role_names),
        "roleNames": "、".join(role_names),
        "roleList": [role_map[role_id] for role_id in role_ids if role_id in role_map],
        "platformTch": bool(user_info.get("platformTch", True)),
        "eduTch": bool(user_info.get("eduTch", True)),
        "tchState": bool(user_info.get("tchState", True)),
        "tchJiaoyanAuth": bool(user_info.get("tchJiaoyanAuth", False)),
        "tchShiziAuth": bool(user_info.get("tchShiziAuth", False)),
        "tchShixunAuth": bool(user_info.get("tchShixunAuth", False)),
        "tchKtslAuth": bool(user_info.get("tchKtslAuth", False)),
        "tchKftdAuth": bool(user_info.get("tchKftdAuth", False)),
        "noticeAuth": bool(user_info.get("noticeAuth", True)),
        "ojPermission": bool(user_info.get("ojPermission", True)),
        "prepareContentAuth": bool(user_info.get("prepareContentAuth", True)),
        "principal": bool(user_info.get("principal", False)),
        "eduId": _coerce_int(user_info.get("eduId") or school_info.get("id")) or 0,
        "schoolName": school_info.get("name") or school_info.get("eduName") or "",
        "createdTime": user_info.get("createdTime") or "",
    }
    if include_subjects:
        row["subjectCurriculumDtoList"] = _json_deep_copy(subject_rows)
        row["subjectCurriculumList"] = _json_deep_copy(subject_rows)
    return row


def _staff_account_rows(store: MirrorStore, *, include_admin: bool = True, include_subjects: bool = False) -> list[dict[str, Any]]:
    rows = [
        _staff_account_row(store, profile, include_subjects=include_subjects)
        for profile in _local_staff_profiles(store, include_admin=include_admin)
    ]
    return sorted(rows, key=lambda row: (_coerce_int(row.get("userId")) or 0, str(row.get("name") or "")))


def _find_staff_profile(
    store: MirrorStore,
    *,
    user_id: Any = None,
    username: str | None = None,
    include_admin: bool = True,
) -> dict[str, Any] | None:
    normalized_user_id = _coerce_int(user_id)
    normalized_username = str(username or "").strip()
    for profile in _local_staff_profiles(store, include_admin=include_admin):
        if normalized_user_id is not None and _profile_user_id_from_profile(profile) == normalized_user_id:
            return profile
        if normalized_username and str(profile.get("username") or "").strip() == normalized_username:
            return profile
    return None


def _next_staff_user_id(store: MirrorStore) -> int:
    max_user_id = 12000
    for profile in _local_staff_profiles(store, include_admin=True):
        max_user_id = max(max_user_id, _profile_user_id_from_profile(profile) or max_user_id)
    return max_user_id + 1


def _persist_local_profile(
    store: MirrorStore,
    *,
    profile_name: str,
    username: str,
    password_hash: str,
    token: str,
    login_content: dict[str, Any],
    fresh_auth: dict[str, Any],
    vuex_state: dict[str, Any],
) -> dict[str, Any]:
    store.store_profile(
        profile_name=profile_name,
        username=username,
        password_hash=password_hash,
        login_path=TEACHER_LOGIN_PATH,
        token=token,
        login_content=login_content,
        fresh_auth=fresh_auth,
        vuex_state=vuex_state,
    )
    return store.get_profile(profile_name) or {}


def _upsert_staff_account_profile(store: MirrorStore, request: Request, submitted: dict[str, Any]) -> dict[str, Any]:
    target_user_id = _parse_int_like(submitted.get("userId") or submitted.get("id"))
    submitted_username = str(
        submitted.get("name") or submitted.get("userName") or submitted.get("username") or ""
    ).strip()
    existing_profile = _find_staff_profile(
        store,
        user_id=target_user_id,
        username=submitted_username,
        include_admin=True,
    )
    source_profile = existing_profile or _resolve_profile(store, request) or store.get_profile("teacher") or {}
    source_profile_name = str((source_profile or {}).get("profile_name") or "teacher")
    user_id = target_user_id or _profile_user_id_from_profile(existing_profile) or _next_staff_user_id(store)
    profile_name = str((existing_profile or {}).get("profile_name") or f"teacher_{user_id}")
    username = submitted_username or str((existing_profile or {}).get("username") or f"teacher{user_id}").strip()
    token = str((existing_profile or {}).get("token") or f"local-teacher-{user_id}-token").strip()
    password_hash = _normalize_local_password_hash(
        submitted.get("password"),
        fallback=str((existing_profile or {}).get("password_hash") or (source_profile or {}).get("password_hash") or ""),
    )

    login_content = _json_deep_copy(
        (existing_profile or {}).get("login_content")
        or (source_profile or {}).get("login_content")
        or {}
    )
    if not isinstance(login_content, dict):
        login_content = {}
    login_content["token"] = token
    permission_tree = _teacher_permission_tree(store, source_profile_name)
    if not permission_tree:
        permission_tree = _minimal_local_teacher_permission_tree()
    if not login_content.get("authTree"):
        login_content["authTree"] = json.dumps({"children": permission_tree}, ensure_ascii=False)

    fresh_auth = _json_deep_copy(
        (existing_profile or {}).get("fresh_auth")
        or (source_profile or {}).get("fresh_auth")
        or {}
    )
    if not isinstance(fresh_auth, dict):
        fresh_auth = {}
    source_user_info = fresh_auth.get("userInfo") if isinstance(fresh_auth.get("userInfo"), dict) else {}
    user_info = _hydrate_teacher_user_info(store, source_user_info, source_profile_name)
    school_info = _hydrate_teacher_school_info(
        store,
        fresh_auth.get("schoolInfo") if isinstance(fresh_auth.get("schoolInfo"), dict) else _teacher_school_info(store, source_profile_name),
        source_profile_name,
    )
    campus_ids = _extract_campus_ids(submitted.get("eduCampusIdList"))
    if not campus_ids:
        campus_ids = _extract_campus_ids(submitted.get("eduCampusId"))
    if not campus_ids and existing_profile is not None:
        campus_ids = _teacher_selected_school_ids(store, profile_name)
    if not campus_ids:
        campus_ids = _teacher_selected_school_ids(store, source_profile_name)
    if not campus_ids:
        campus_ids = _extract_campus_ids(school_info.get("eduCampusId"))
    if campus_ids:
        primary_campus_id = campus_ids[0]
        school_info["eduCampusId"] = primary_campus_id
        school_info["educationalInstitutionCampusId"] = primary_campus_id
        school_info["educational_institution_campus_id"] = primary_campus_id
        school_info["campusId"] = primary_campus_id

    role_ids = _extract_int_list(submitted.get("eduRoleIdList"))
    if not role_ids:
        role_ids = _extract_int_list(submitted.get("roleIdList"))
    if not role_ids and existing_profile is not None:
        role_ids = _staff_role_ids(profile_name, existing_profile, _teacher_user_info(store, profile_name))
    if not role_ids:
        role_ids = [1]
    role_rows = [
        role_row
        for role_row in _local_staff_role_rows()
        if (_coerce_int(role_row.get("id")) or _coerce_int(role_row.get("roleId"))) in role_ids
    ]
    if not role_rows:
        role_rows = [_local_staff_role_rows()[0]]
    role_ids = [_coerce_int(role_row.get("id")) or _coerce_int(role_row.get("roleId")) or 1 for role_row in role_rows]
    role_names = [
        str(role_row.get("roleName") or role_row.get("name") or role_id)
        for role_id, role_row in zip(role_ids, role_rows)
    ]

    subject_rows = submitted.get("subjectCurriculumDtoList")
    if not isinstance(subject_rows, list):
        subject_rows = submitted.get("subjectCurriculumList")
    if not isinstance(subject_rows, list) or not subject_rows:
        if existing_profile is not None:
            subject_rows = _staff_subject_curriculum_rows(store, profile_name, _teacher_user_info(store, profile_name))
        else:
            subject_rows = _default_staff_subject_curriculum_rows(store)

    state_value = _normalized_optional_filter_text(submitted.get("state")) or str(user_info.get("state") or "在职")
    sex_value = _normalized_optional_filter_text(submitted.get("sex")) or str(user_info.get("sex") or "")
    full_or_part_value = _normalized_optional_filter_text(submitted.get("isFullOrPart")) or str(user_info.get("isFullOrPart") or "")
    real_name = str(
        submitted.get("realName")
        or submitted.get("realname")
        or user_info.get("realName")
        or user_info.get("realname")
        or username
    ).strip()

    user_info["id"] = user_id
    user_info["userId"] = user_id
    user_info["name"] = username
    user_info["username"] = username
    user_info["realName"] = real_name
    user_info["realname"] = real_name
    user_info["nickName"] = str(submitted.get("nickName") or user_info.get("nickName") or "").strip()
    user_info["sex"] = sex_value
    user_info["phoneNum"] = str(submitted.get("phoneNum") or user_info.get("phoneNum") or "").strip()
    user_info["state"] = state_value
    user_info["isFullOrPart"] = full_or_part_value
    user_info["eduCampusIdList"] = _json_deep_copy(campus_ids)
    user_info["eduRoleIdList"] = _json_deep_copy(role_ids)
    user_info["roleIdList"] = _json_deep_copy(role_ids)
    user_info["roleNames"] = "、".join(role_names)
    user_info["subjectCurriculumDtoList"] = _json_deep_copy(subject_rows)
    user_info["subjectCurriculumList"] = _json_deep_copy(subject_rows)
    user_info["platformTch"] = bool(submitted.get("platformTch", user_info.get("platformTch", True)))
    user_info["eduTch"] = bool(submitted.get("eduTch", user_info.get("eduTch", True)))
    user_info["tchState"] = bool(submitted.get("tchState")) if "tchState" in submitted else bool(user_info.get("tchState", True))
    user_info["tchJiaoyanAuth"] = bool(submitted.get("tchJiaoyanAuth", user_info.get("tchJiaoyanAuth", False)))
    user_info["tchShiziAuth"] = bool(submitted.get("tchShiziAuth", user_info.get("tchShiziAuth", False)))
    user_info["tchShixunAuth"] = bool(submitted.get("tchShixunAuth", user_info.get("tchShixunAuth", False)))
    user_info["tchKtslAuth"] = bool(submitted.get("tchKtslAuth", user_info.get("tchKtslAuth", False)))
    user_info["tchKftdAuth"] = bool(submitted.get("tchKftdAuth", user_info.get("tchKftdAuth", False)))
    user_info["noticeAuth"] = bool(submitted.get("noticeAuth", user_info.get("noticeAuth", True)))
    user_info["ojPermission"] = bool(submitted.get("ojPermission", user_info.get("ojPermission", True)))
    user_info["prepareContentAuth"] = bool(submitted.get("prepareContentAuth", user_info.get("prepareContentAuth", True)))
    if "userImageUrl" in submitted:
        user_info["userImageUrl"] = str(submitted.get("userImageUrl") or "").strip() or user_info.get("userImageUrl") or DEFAULT_HOMEPAGE_AVATAR_URL

    fresh_auth["identity"] = 1
    fresh_auth["userInfo"] = _json_deep_copy(user_info)
    fresh_auth["schoolInfo"] = _json_deep_copy(school_info)
    fresh_auth["roleList"] = _json_deep_copy(role_rows)

    vuex_state = _json_deep_copy(
        (existing_profile or {}).get("vuex_state")
        or (source_profile or {}).get("vuex_state")
        or {}
    )
    if not isinstance(vuex_state, dict):
        vuex_state = {}
    user_state = vuex_state.get("user")
    if not isinstance(user_state, dict):
        user_state = {}
        vuex_state["user"] = user_state
    user_state["token"] = token
    user_state["adminToken"] = user_state.get("adminToken") or token
    user_state["username"] = username
    user_state["adminUserName"] = username
    user_state["identity"] = 1
    user_state["selected_schools"] = _json_deep_copy(campus_ids)
    if not isinstance(user_state.get("permisionList"), list) or not user_state.get("permisionList"):
        user_state["permisionList"] = _json_deep_copy(permission_tree)
    if not isinstance(user_state.get("adminpermisionList"), list) or not user_state.get("adminpermisionList"):
        user_state["adminpermisionList"] = _json_deep_copy(
            _teacher_admin_permissions(store, source_profile_name) or _build_admin_permission_tree(permission_tree)
        )
    user_state["userInfo"] = _json_deep_copy(user_info)
    user_state["schoolInfo"] = _json_deep_copy(school_info)

    return _persist_local_profile(
        store,
        profile_name=profile_name,
        username=username,
        password_hash=password_hash,
        token=token,
        login_content=login_content,
        fresh_auth=fresh_auth,
        vuex_state=vuex_state,
    )


def _teacher_directory_rows(store: MirrorStore) -> list[dict[str, Any]]:
    teacher_profile = store.get_profile("teacher") or {}
    teacher_fresh_auth = teacher_profile.get("fresh_auth") or {}
    teacher_vuex_user = (teacher_profile.get("vuex_state") or {}).get("user") or {}
    teacher_user_info = teacher_fresh_auth.get("userInfo") or {}
    campus_id = _teacher_primary_campus_id(store)
    campus_name = _teacher_primary_campus_name(store)

    rows_by_id: dict[str, dict[str, Any]] = {}

    def merge_row(candidate: Any) -> None:
        if not isinstance(candidate, dict):
            return

        row_id = (
            candidate.get("id")
            or candidate.get("userId")
            or candidate.get("tchId")
            or candidate.get("teacherId")
            or candidate.get("code")
            or candidate.get("name")
            or teacher_profile.get("username")
            or "teacher"
        )
        row_key = str(row_id)
        current = _json_deep_copy(rows_by_id.get(row_key, {}))
        incoming = _json_deep_copy(candidate)
        for key, value in incoming.items():
            if current.get(key) in (None, "", [], {}) and value not in (None, "", [], {}):
                current[key] = value

        current["id"] = current.get("id") or candidate.get("id") or _teacher_admin_user_id(store)
        current["userId"] = current.get("userId") or current.get("id")
        current["teacherId"] = current.get("teacherId") or current.get("id")
        current["tchId"] = current.get("tchId") or current.get("id")
        current["name"] = current.get("name") or teacher_profile.get("username") or ""
        current["username"] = current.get("username") or current.get("name") or teacher_profile.get("username") or ""
        real_name = current.get("realName") or current.get("realname") or current.get("name") or ""
        current["realName"] = real_name
        current["realname"] = real_name
        if campus_id is not None:
            current.setdefault("eduCampusId", campus_id)
            current.setdefault("educationalInstitutionCampusId", campus_id)
            current.setdefault("educational_institution_campus_id", campus_id)
            current.setdefault("campusId", campus_id)
            current.setdefault("dept_id", campus_id)
        if campus_name:
            current.setdefault("campusName", campus_name)
        current.setdefault("state", "鍦ㄨ亴")
        current.setdefault("platformTch", True)
        current.setdefault("eduTch", True)
        current.setdefault("noticeAuth", bool(current.get("noticeAuth", True)))
        current.setdefault("ojPermission", bool(current.get("ojPermission", False)))
        current.setdefault("prepareContentAuth", bool(current.get("prepareContentAuth", False)))
        rows_by_id[row_key] = current

    for key in ("eduTchList", "tchList", "teacherList"):
        rows = teacher_vuex_user.get(key)
        if isinstance(rows, list):
            for row in rows:
                merge_row(row)

    merge_row(
        {
            "id": teacher_user_info.get("id"),
            "userId": teacher_user_info.get("id"),
            "name": teacher_user_info.get("name") or teacher_profile.get("username") or "",
            "username": teacher_profile.get("username") or teacher_user_info.get("name") or "",
            "realName": teacher_user_info.get("realName") or teacher_user_info.get("realname") or "",
            "realname": teacher_user_info.get("realname") or teacher_user_info.get("realName") or "",
            "phoneNum": teacher_user_info.get("phoneNum") or "",
            "sex": teacher_user_info.get("sex") or "",
            "userImageUrl": teacher_user_info.get("userImageUrl") or "",
            "cardImgUrl": teacher_user_info.get("cardImgUrl"),
            "createdTime": teacher_user_info.get("createdTime") or "",
            "expireTime": teacher_user_info.get("expireTime"),
            "state": teacher_user_info.get("state") or "鍦ㄨ亴",
            "principal": teacher_user_info.get("principal", False),
            "noticeAuth": teacher_user_info.get("noticeAuth", True),
            "ojPermission": teacher_user_info.get("ojPermission", False),
            "prepareContentAuth": teacher_user_info.get("prepareContentAuth", False),
            "code": teacher_user_info.get("code") or "",
            "eduId": teacher_user_info.get("eduId"),
        }
    )

    for local_row in _staff_account_rows(store, include_admin=False):
        merge_row(local_row)

    return sorted(
        rows_by_id.values(),
        key=lambda row: (
            0 if _coerce_int(row.get("id")) is not None else 1,
            _coerce_int(row.get("id")) or 0,
            str(row.get("name") or ""),
        ),
    )


def _teacher_class_count(store: MirrorStore) -> int:
    class_ids: set[int] = set()
    for plan in store.list_teaching_plans():
        if not isinstance(plan, dict):
            continue
        class_info = plan.get("classInfo") or {}
        class_id = _coerce_int((class_info or {}).get("id") or plan.get("curriculum_class_id"))
        if class_id is not None:
            class_ids.add(class_id)
    return len(class_ids)


def _teacher_subject_activity_counts(store: MirrorStore) -> dict[int, int]:
    counts: dict[int, int] = {}
    for plan in store.list_teaching_plans():
        if not isinstance(plan, dict):
            continue
        subject_id = _coerce_int(plan.get("subject_id"))
        if subject_id is None:
            continue
        counts[subject_id] = counts.get(subject_id, 0) + 1
    return counts


def _build_admin_latest_total_info(store: MirrorStore) -> dict[str, Any]:
    school_info = _hydrate_teacher_school_info(store, _teacher_school_info(store))
    teacher_rows = _teacher_directory_rows(store)
    subject_rows = _teacher_subject_catalog(store)
    local_students = store.list_local_students()
    campus_rows = store.list_user_campuses()
    teaching_plan_count = len(store.list_teaching_plans())
    class_count = _teacher_class_count(store)
    curriculum_count = len(store.list_campus_curriculum_auths())

    content = _json_deep_copy(school_info)
    content.setdefault("id", school_info.get("id") or 0)
    content.setdefault("eduName", school_info.get("eduName") or school_info.get("name") or "")
    content.setdefault("eduDomain", school_info.get("eduDomain") or school_info.get("domain") or "")
    content.setdefault("offTime", school_info.get("offTime") or school_info.get("off_time") or "")
    content.setdefault("themeColor", school_info.get("themeColor") or "#1778FF")
    content.setdefault("pointAuth", bool(school_info.get("pointAuth")))
    content.setdefault("questionBankPermission", bool(school_info.get("questionBankPermission")))
    content.setdefault("prepareContentAuth", bool(school_info.get("prepareContentAuth")))
    content.setdefault("ojPermission", bool(school_info.get("ojPermission")))
    content["maxStudentNum"] = _coerce_int(content.get("maxStudentNum")) or 0
    content["maxTeacherNum"] = _coerce_int(content.get("maxTeacherNum")) or 0
    content["stuRemainTime"] = _coerce_int(content.get("stuRemainTime")) or 0
    content["try_school_num"] = 0
    content["user_num"] = len(teacher_rows)
    content["school_use_stu_time_num"] = 0
    content["try_class_num"] = 0
    content["normal_class_num"] = class_count
    content["intended_stu_num"] = 0
    content["try_stu_num"] = 0
    content["signed_tchplan_num"] = teaching_plan_count
    content["signed_stu_tchplan_num"] = teaching_plan_count
    content["created_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content["teacherNum"] = len(teacher_rows)
    content["platformTchNum"] = len(teacher_rows)
    content["studentNum"] = len(local_students)
    content["activeStuNum"] = len(local_students)
    content["normalStuNum"] = len(local_students)
    content["campusNum"] = len(campus_rows) or (1 if school_info else 0)
    content["currentCampusNum"] = content["campusNum"]
    content["subjectNum"] = len(subject_rows)
    content["currentSubjectNum"] = len(subject_rows)
    content["curriculumNum"] = curriculum_count
    content["currentCurriculumNum"] = curriculum_count
    content["classNum"] = class_count
    content["currentClassNum"] = class_count
    content["tchPlanNum"] = teaching_plan_count
    content["schoolNum"] = 1 if school_info else 0
    content["normalSchoolNum"] = 1 if school_info else 0
    return content


def _build_admin_subject_stat_rows(store: MirrorStore) -> list[dict[str, Any]]:
    school_info = _hydrate_teacher_school_info(store, _teacher_school_info(store))
    school_name = school_info.get("eduName") or school_info.get("name") or ""
    subject_activity = _teacher_subject_activity_counts(store)
    rows: list[dict[str, Any]] = []
    for subject in _teacher_subject_catalog(store):
        subject_id = _coerce_int(subject.get("id"))
        if subject_id is None:
            continue
        subject_name = str(subject.get("name") or subject.get("subject_name") or f"Subject {subject_id}")
        activity_count = subject_activity.get(subject_id, 0)
        rows.append(
            {
                "id": subject_id,
                "subjectId": subject_id,
                "subject_id": subject_id,
                "code": subject.get("code") or subject_id,
                "name": subject_name,
                "subjectName": subject_name,
                "subject_name": subject_name,
                "subjectInfo": {
                    "id": subject_id,
                    "subjectId": subject_id,
                    "name": subject_name,
                    "subjectName": subject_name,
                },
                "schoolName": school_name,
                "eduName": school_name,
                "schoolNum": 1,
                "studentNum": activity_count,
                "stuNum": activity_count,
                "normalStuNum": activity_count,
                "count": activity_count,
                "num": activity_count,
                "value": activity_count,
            }
        )
    return rows


def _build_admin_subject_list(store: MirrorStore) -> list[dict[str, Any]]:
    subjects = store.list_campus_subjects()
    if subjects:
        return [_json_deep_copy(subject) for subject in subjects]
    return [_json_deep_copy(subject) for subject in _teacher_subject_catalog(store)]


def _teacher_subject_catalog(store: MirrorStore) -> list[dict[str, Any]]:
    subjects_by_id: dict[int, dict[str, Any]] = {}

    def merge_subject(candidate: Any) -> None:
        if not isinstance(candidate, dict):
            return
        subject_id = _coerce_int(candidate.get("id") or candidate.get("subject_id") or candidate.get("subjectId"))
        if subject_id is None:
            return

        current = _json_deep_copy(subjects_by_id.get(subject_id, {}))
        incoming = _json_deep_copy(candidate)
        for key, value in incoming.items():
            if key == "name":
                current_name = _non_placeholder_subject_name(current.get("name"), subject_id)
                incoming_name = _non_placeholder_subject_name(value, subject_id)
                if current_name is None and incoming_name is not None:
                    current["name"] = incoming_name
                continue
            if current.get(key) in (None, "", [], {}) and value not in (None, "", [], {}):
                current[key] = value

        current["id"] = subject_id
        if _non_placeholder_subject_name(current.get("name"), subject_id) is None:
            for key in ("subjectName", "subject_name", "title"):
                value = _non_placeholder_subject_name(current.get(key), subject_id)
                if value is not None:
                    current["name"] = value
                    break
        if _non_placeholder_subject_name(current.get("name"), subject_id) is None:
            current["name"] = f"Subject {subject_id}"
        current.setdefault("code", subject_id)
        current.setdefault("sort_num", subject_id)
        subjects_by_id[subject_id] = current

    for subject in store.list_campus_subjects():
        merge_subject(subject)

    for entry in store.list_campus_curriculum_auths():
        if not isinstance(entry, dict):
            continue
        curriculum_info = entry.get("curriculumInfo") or {}
        if not isinstance(curriculum_info, dict):
            continue
        merge_subject(
            {
                "id": curriculum_info.get("subject_id") or entry.get("subject_id"),
                "name": entry.get("subjectName") or curriculum_info.get("subjectName") or curriculum_info.get("subject_name"),
            }
        )

    for plan in store.list_teaching_plans():
        if not isinstance(plan, dict):
            continue
        class_info = plan.get("classInfo") or {}
        if isinstance(class_info, dict):
            for subject in class_info.get("subjectInfoList") or []:
                merge_subject(subject)
        merge_subject({"id": plan.get("subject_id")})

    for subject in DEFAULT_TEACHER_SUBJECT_ROWS:
        merge_subject(subject)

    return sorted(
        subjects_by_id.values(),
        key=lambda subject: (
            _coerce_int(subject.get("sort_num")) or subject["id"],
            subject["id"],
        ),
    )


def _merge_subject_rows(existing_rows: Any, fallback_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    subjects_by_id: dict[int, dict[str, Any]] = {}

    def merge_subject(candidate: Any) -> None:
        if not isinstance(candidate, dict):
            return
        subject_id = _coerce_int(candidate.get("id") or candidate.get("subject_id") or candidate.get("subjectId"))
        if subject_id is None:
            return

        current = _json_deep_copy(subjects_by_id.get(subject_id, {}))
        incoming = _json_deep_copy(candidate)
        for key, value in incoming.items():
            if key == "name":
                current_name = _non_placeholder_subject_name(current.get("name"), subject_id)
                incoming_name = _non_placeholder_subject_name(value, subject_id)
                if current_name is None and incoming_name is not None:
                    current["name"] = incoming_name
                continue
            if current.get(key) in (None, "", [], {}) and value not in (None, "", [], {}):
                current[key] = value

        current["id"] = subject_id
        if _non_placeholder_subject_name(current.get("name"), subject_id) is None:
            for key in ("subjectName", "subject_name", "title"):
                value = _non_placeholder_subject_name(current.get(key), subject_id)
                if value is not None:
                    current["name"] = value
                    break
        if _non_placeholder_subject_name(current.get("name"), subject_id) is None:
            current["name"] = f"Subject {subject_id}"
        current.setdefault("code", subject_id)
        current.setdefault("sort_num", subject_id)
        subjects_by_id[subject_id] = current

    if isinstance(existing_rows, list):
        for subject in existing_rows:
            merge_subject(subject)
    for subject in fallback_rows:
        merge_subject(subject)

    return sorted(
        subjects_by_id.values(),
        key=lambda subject: (
            _coerce_int(subject.get("sort_num")) or subject["id"],
            subject["id"],
        ),
    )


def _teacher_subject_name_map(store: MirrorStore) -> dict[int, str]:
    subject_names: dict[int, str] = {}
    for subject in _teacher_subject_catalog(store):
        subject_id = _coerce_int(subject.get("id"))
        name = subject.get("name")
        if subject_id is None or name in (None, ""):
            continue
        subject_names[subject_id] = str(name)
    return subject_names


def _curriculum_row_from_auth_entry(
    store: MirrorStore,
    entry: dict[str, Any],
    subject_name_map: dict[int, str],
) -> dict[str, Any] | None:
    curriculum_info = entry.get("curriculumInfo") or {}
    if not isinstance(curriculum_info, dict):
        return None

    row = _json_deep_copy(curriculum_info)
    subject_id = _coerce_int(row.get("subject_id") or entry.get("subject_id"))
    row["campusAuthId"] = entry.get("id")
    row["id"] = row.get("id") or entry.get("curriculum_id") or entry.get("id")
    row["price"] = entry.get("price", row.get("price"))
    row["campusName"] = entry.get("campusName") or row.get("campusName") or _teacher_primary_campus_name(store)
    row["created_time"] = row.get("created_time") or entry.get("created_time")
    if row.get("educational_institution_id") in (None, ""):
        row["educational_institution_id"] = entry.get("educational_institution_id")
    if row.get("educational_institution_campus_id") in (None, ""):
        row["educational_institution_campus_id"] = (
            entry.get("educational_institution_campus_id") or _teacher_primary_campus_id(store) or 0
        )

    subject_name = (
        entry.get("subjectName")
        or row.get("subjectName")
        or row.get("subject_name")
        or subject_name_map.get(subject_id or -1)
        or ""
    )
    row["subjectName"] = subject_name
    row["subject_name"] = subject_name
    if row.get("state") in (None, ""):
        row["state"] = "姝ｅ父"
    if "is_effective" not in row:
        row["is_effective"] = True
    return row


def _curriculum_materials_by_curriculum(store: MirrorStore) -> dict[int, list[dict[str, Any]]]:
    materials_by_curriculum: dict[int, list[dict[str, Any]]] = {}
    for material in store.list_curriculum_materials():
        if not isinstance(material, dict):
            continue
        curriculum_id = _coerce_int(material.get("curriculum_id"))
        if curriculum_id is None:
            continue
        materials_by_curriculum.setdefault(curriculum_id, []).append(_json_deep_copy(material))

    for rows in materials_by_curriculum.values():
        rows.sort(
            key=lambda row: (
                _coerce_int(row.get("sort_num") or row.get("sortNum")) or 0,
                _coerce_int(row.get("id")) or 0,
            )
        )
    return materials_by_curriculum


def _page_window(request: Request, *, default_page_size: int = 20) -> tuple[int, int, int]:
    page_no = _coerce_int(_first_query_value(request, "page_no")) or 1
    page_size = _coerce_int(_first_query_value(request, "page_size")) or default_page_size
    page_no = max(page_no, 1)
    page_size = max(page_size, 1)
    return page_no, page_size, (page_no - 1) * page_size


def _page_request_window(payload: Any, *, default_page_size: int = 20) -> tuple[int, int]:
    body = payload if isinstance(payload, dict) else {}
    page_request = body.get("pageRequest") if isinstance(body.get("pageRequest"), dict) else {}
    page_num = _parse_int_like(
        body.get("pageNum")
        or body.get("page_no")
        or body.get("pageNo")
        or page_request.get("pageNum")
        or page_request.get("page_no")
        or page_request.get("pageNo")
    ) or 1
    page_size = _parse_int_like(
        body.get("pageSize")
        or body.get("page_size")
        or body.get("pageSizeNum")
        or page_request.get("pageSize")
        or page_request.get("page_size")
        or page_request.get("pageSizeNum")
    ) or default_page_size
    return max(page_num, 1), max(page_size, 1)


def _synthetic_request(query_string: str = "") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "root_path": "",
        "scheme": "http",
        "query_string": query_string.encode("utf-8"),
        "headers": [],
        "client": ("127.0.0.1", 0),
        "server": ("127.0.0.1", 80),
        "app": None,
    }
    return Request(scope)


def _teacher_subject_snapshot(store: MirrorStore, subject_code: str | None = None) -> dict[str, str]:
    normalized_code = (subject_code or "").strip()
    matched_subject: dict[str, Any] | None = None
    for subject in _teacher_subject_catalog(store):
        candidate_codes = {
            str(subject.get("code") or "").strip(),
            str(subject.get("id") or "").strip(),
        }
        if normalized_code and normalized_code in candidate_codes:
            matched_subject = subject
            break
        if matched_subject is None:
            matched_subject = subject

    resolved_code = (
        normalized_code
        or str((matched_subject or {}).get("code") or "").strip()
        or str((matched_subject or {}).get("id") or "").strip()
        or "0"
    )
    resolved_name = str(
        (matched_subject or {}).get("name")
        or (matched_subject or {}).get("subjectName")
        or (matched_subject or {}).get("subject_name")
        or ""
    )
    return {"subjectCode": resolved_code, "subjectName": resolved_name}


def _extract_int_list(raw_value: Any) -> list[int]:
    values: list[int] = []
    if raw_value in (None, ""):
        return values
    if isinstance(raw_value, (list, tuple, set)):
        for item in raw_value:
            _append_unique_int(values, item)
        return values
    if isinstance(raw_value, dict):
        for item in raw_value.values():
            _append_unique_int(values, item)
        return values

    text = str(raw_value).strip()
    if not text:
        return values
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = None
    if parsed is not None and parsed != text:
        return _extract_int_list(parsed)

    for part in re.split(r"[\[\],\s]+", text):
        _append_unique_int(values, part)
    return values


def _extract_campus_ids(raw_value: Any) -> list[int]:
    campus_ids: list[int] = []
    if raw_value in (None, ""):
        return campus_ids
    if isinstance(raw_value, (list, tuple, set)):
        for item in raw_value:
            _append_unique_int(campus_ids, item)
        return campus_ids
    if isinstance(raw_value, dict):
        for key in ("campusIds", "campusIdArr", "campusId", "eduCampusId"):
            if key in raw_value:
                return _extract_campus_ids(raw_value[key])
        return campus_ids

    text = str(raw_value).strip()
    if not text:
        return campus_ids
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = None
    if parsed is not None and parsed != text:
        if isinstance(parsed, (list, tuple, set, dict)):
            return _extract_campus_ids(parsed)
        _append_unique_int(campus_ids, parsed)
        return campus_ids

    for part in re.split(r"[\[\],\s]+", text):
        _append_unique_int(campus_ids, part)
    return campus_ids


def _build_campus_curriculum_auth_rows(store: MirrorStore, request: Request) -> list[dict[str, Any]]:
    subject_id_filter = _first_query_value(request, "subjectId") or _first_query_value(request, "subject_id")
    teaching_type_filter = _first_query_value(request, "teaching_type")
    curriculum_type_filter = _first_query_value(request, "curriculum_type")
    requested_campus_ids = _extract_campus_ids(_first_query_value(request, "campusIds"))
    if not requested_campus_ids:
        requested_campus_ids = _extract_campus_ids(_first_query_value(request, "campusIdArr"))
    subject_name_map = _teacher_subject_name_map(store)

    rows: list[dict[str, Any]] = []
    for entry in store.list_campus_curriculum_auths():
        if not isinstance(entry, dict):
            continue

        row = _curriculum_row_from_auth_entry(store, entry, subject_name_map)
        if row is None:
            continue
        _normalize_curriculum_storage_fields(row)

        campus_id = _coerce_int(
            entry.get("educational_institution_campus_id")
            or row.get("educational_institution_campus_id")
            or _teacher_primary_campus_id(store)
        )
        if requested_campus_ids and campus_id not in requested_campus_ids:
            continue
        if subject_id_filter and str(row.get("subject_id") or "") != subject_id_filter:
            continue
        if teaching_type_filter and str(row.get("teaching_type") or "") != teaching_type_filter:
            continue
        if curriculum_type_filter and str(row.get("curriculum_type") or "") != curriculum_type_filter:
            continue

        normalized_entry = _json_deep_copy(entry)
        normalized_entry.setdefault("curriculum_id", row.get("id"))
        normalized_entry.setdefault("subject_id", row.get("subject_id"))
        normalized_entry.setdefault("subjectName", row.get("subjectName") or "")
        normalized_entry.setdefault("campusName", row.get("campusName") or _teacher_primary_campus_name(store))
        normalized_entry.setdefault("educational_institution_campus_id", campus_id or 0)
        normalized_entry.setdefault("price", row.get("price") or 0)
        if not isinstance(normalized_entry.get("curriculumInfo"), dict):
            normalized_entry["curriculumInfo"] = {}
        for key, value in row.items():
            normalized_entry["curriculumInfo"].setdefault(key, value)
        rows.append(normalized_entry)

    rows.sort(
        key=lambda entry: (
            _coerce_int((entry.get("curriculumInfo") or {}).get("sort_num")) or 0,
            _coerce_int((entry.get("curriculumInfo") or {}).get("id") or entry.get("curriculum_id")) or 0,
        )
    )
    return rows


def _default_header_rows(table_type: str) -> list[dict[str, Any]]:
    if table_type == "TCH_XMORDERINFO":
        return [
            {"code": "3", "selected": 1, "headDesc": "订单类型", "prop": "orderType"},
            {"code": "4", "selected": 1, "headDesc": "购买项目", "prop": "xmOrderGoodsStr"},
            {"code": "5", "selected": 1, "headDesc": "应收/应退", "prop": "amountOfMoney"},
            {"code": "6", "selected": 1, "headDesc": "实收/实退", "prop": "amountOfMoney1"},
            {"code": "7", "selected": 1, "headDesc": "欠费金额(元)", "prop": "unpaid_amount"},
            {"code": "8", "selected": 1, "headDesc": "业绩归属", "prop": "belong_user_str"},
            {"code": "9", "selected": 1, "headDesc": "创建时间", "prop": "created_time"},
            {"code": "10", "selected": 1, "headDesc": "最近支付时间", "prop": "last_pay_time"},
            {"code": "11", "selected": 1, "headDesc": "经办时间", "prop": "deal_date"},
            {"code": "12", "selected": 1, "headDesc": "订单状态", "prop": "state"},
        ]
    return []


def _build_competition_source_info(store: MirrorStore, source_id: Any) -> dict[str, Any]:
    source = store.find_competition_source(source_id)
    if source is None:
        return {}
    return _json_deep_copy(source)


def _build_teacher_curriculum_rows(store: MirrorStore, request: Request) -> list[dict[str, Any]]:
    requested_subject_ids = _extract_request_int_set(
        request,
        None,
        "subject_id",
        "subject_ids",
        "subjectId",
        "subjectIds",
    )
    subject_id_filter = _first_query_value(request, "subject_id")
    teaching_type_filter = _first_query_value(request, "teaching_type")
    curriculum_type_filter = _first_query_value(request, "course_type") or _first_query_value(request, "curriculum_type")
    curriculum_title_filter = (_first_query_value(request, "curriculumTitle") or "").strip().lower()
    lesson_title_filter = (_first_query_value(request, "lessonTitle") or "").strip().lower()
    context_class_id = _resolve_class_context_id(request)
    context_class_row = store.find_class(context_class_id) or {} if context_class_id is not None else {}
    context_subject_ids = {
        subject_id
        for subject_id in (
            _coerce_int(value)
            for value in (context_class_row.get("subjectIdList") or context_class_row.get("subject_id_list") or [])
        )
        if subject_id is not None
    }
    context_curriculum_ids = {
        curriculum_id
        for curriculum_id in (
            _coerce_int(value)
            for value in (
                context_class_row.get("curriculumIdList") or context_class_row.get("curriculum_id_list") or []
            )
        )
        if curriculum_id is not None
    }

    subject_name_map = _teacher_subject_name_map(store)
    materials_by_curriculum = _curriculum_materials_by_curriculum(store)
    curriculum_plan_counts: dict[int, int] = {}
    for plan in store.list_teaching_plans():
        if not isinstance(plan, dict):
            continue
        curriculum_id = _coerce_int(plan.get("curriculum_id"))
        if curriculum_id is None:
            continue
        curriculum_plan_counts[curriculum_id] = curriculum_plan_counts.get(curriculum_id, 0) + 1

    rows: list[dict[str, Any]] = []
    for entry in store.list_campus_curriculum_auths():
        if not isinstance(entry, dict):
            continue
        row = _curriculum_row_from_auth_entry(store, entry, subject_name_map)
        if row is None:
            continue

        curriculum_id = _coerce_int(row.get("id"))
        if curriculum_id is None:
            continue
        material_rows = materials_by_curriculum.get(curriculum_id, [])
        lesson_titles = [str(material.get("title") or "") for material in material_rows if material.get("title")]

        row["curriculumMaterialList"] = _json_deep_copy(material_rows)
        row["curriculumMaterialNum"] = len(material_rows)
        row["lessonTitleList"] = lesson_titles
        row["teachingPlanNum"] = curriculum_plan_counts.get(curriculum_id, 0)
        _normalize_curriculum_storage_fields(row, material_rows)
        if row.get("img_url") in (None, ""):
            for material in material_rows:
                if material.get("img_url"):
                    row["img_url"] = material["img_url"]
                    break

        if context_curriculum_ids and curriculum_id not in context_curriculum_ids:
            continue
        if context_subject_ids and (_coerce_int(row.get("subject_id")) not in context_subject_ids):
            continue
        if requested_subject_ids and (_coerce_int(row.get("subject_id")) not in requested_subject_ids):
            continue
        if subject_id_filter and str(row.get("subject_id") or "") != subject_id_filter:
            continue
        if teaching_type_filter and str(row.get("teaching_type") or "") != teaching_type_filter:
            continue
        if curriculum_type_filter and str(row.get("curriculum_type") or "") != curriculum_type_filter:
            continue
        if curriculum_title_filter and curriculum_title_filter not in str(row.get("title") or "").lower():
            continue
        if lesson_title_filter and not any(lesson_title_filter in title.lower() for title in lesson_titles):
            continue

        rows.append(row)

    return rows


def _build_curriculum_title_rows(store: MirrorStore) -> list[dict[str, Any]]:
    subject_name_map = _teacher_subject_name_map(store)
    rows: list[dict[str, Any]] = []
    for entry in store.list_campus_curriculum_auths():
        if not isinstance(entry, dict):
            continue
        row = _curriculum_row_from_auth_entry(store, entry, subject_name_map)
        if row is None:
            continue
        rows.append(
            {
                "id": row.get("id"),
                "curriculum_id": row.get("id"),
                "title": row.get("title") or "",
                "subject_id": row.get("subject_id"),
                "subjectName": row.get("subjectName") or "",
                "subject_name": row.get("subject_name") or "",
                "teaching_type": row.get("teaching_type"),
                "curriculum_type": row.get("curriculum_type"),
                "campusName": row.get("campusName") or "",
                "img_url": row.get("img_url") or "",
            }
        )
    return rows


def _build_teacher_class_rows(store: MirrorStore, request: Request) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    subject_id_filter = _first_query_value(request, "subject_id")
    teaching_type_filter = _first_query_value(request, "teaching_type")
    name_filter = (_first_query_value(request, "name") or _first_query_value(request, "classname") or "").strip().lower()
    course_week_filter = (_first_query_value(request, "course_week") or "").strip()
    course_time_filter = (_first_query_value(request, "course_time") or "").strip().lower()
    end_class_state_filter = _first_query_value(request, "end_class_state")
    deleted_class_ids = {
        class_id
        for class_id in (
            _coerce_int((local_row or {}).get("id"))
            for local_row in store.list_local_classes()
            if isinstance(local_row, dict) and _coerce_int((local_row or {}).get("deleted"))
        )
        if class_id is not None
    }

    subject_name_map = _teacher_subject_name_map(store)
    materials = store.list_curriculum_materials()
    materials_by_id: dict[int, dict[str, Any]] = {}
    default_img_url = "/_external/wugecdn.steam.fun/resources/static/homepage/person-icon.jpeg"
    for material in materials:
        if not isinstance(material, dict):
            continue
        material_id = _coerce_int(material.get("id"))
        if material_id is not None:
            materials_by_id[material_id] = material
        if default_img_url.endswith("person-icon.jpeg") and material.get("img_url"):
            default_img_url = str(material["img_url"])

    grouped_rows: dict[int, dict[str, Any]] = {}
    user_subjects: dict[int, dict[str, Any]] = {}
    for class_entry in store.list_classes():
        if not isinstance(class_entry, dict):
            continue
        class_id = _coerce_int(class_entry.get("id"))
        if class_id is None:
            continue

        row = grouped_rows.setdefault(
            class_id,
            {
                "id": class_id,
                "name": class_entry.get("name") or class_entry.get("className") or f"Class {class_id}",
                "img_url_list": [],
                "teachingPlanLessonImgUrl": [],
                "subjectNameList": [],
                "tchPlanNum": 0,
                "curriculumNum": 0,
                "curriculum_class_type": class_entry.get("curriculum_class_type") or 1,
                "week_json": class_entry.get("week_json") or [],
                "week_str": class_entry.get("week_str") or "",
                "time_str": class_entry.get("time_str") or "",
                "teaching_type": class_entry.get("teaching_type") or 1,
                "end_class_state": class_entry.get("end_class_state"),
                "educational_institution_campus_id": (
                    class_entry.get("educational_institution_campus_id")
                    or _teacher_primary_campus_id(store)
                    or 0
                ),
                "campusName": class_entry.get("campusName") or _teacher_primary_campus_name(store),
                "_subject_names": [],
                "_subject_ids": [],
                "_curriculum_ids": [],
            },
        )

        for subject in class_entry.get("subjectInfoList") or []:
            if not isinstance(subject, dict):
                continue
            info_subject_id = _coerce_int(subject.get("id"))
            info_subject_name = subject.get("name") or subject_name_map.get(info_subject_id or -1)
            if info_subject_id is not None and info_subject_id not in row["_subject_ids"]:
                row["_subject_ids"].append(info_subject_id)
            if info_subject_name:
                _append_unique_text(row["_subject_names"], info_subject_name)
                if info_subject_id is not None:
                    user_subjects[info_subject_id] = {"id": info_subject_id, "name": str(info_subject_name)}

        for subject_id in (
            _coerce_int(value) for value in (class_entry.get("subjectIdList") or class_entry.get("subject_id_list") or [])
        ):
            if subject_id is None or subject_id in row["_subject_ids"]:
                continue
            row["_subject_ids"].append(subject_id)
            subject_name = subject_name_map.get(subject_id)
            if subject_name:
                _append_unique_text(row["_subject_names"], subject_name)
                user_subjects.setdefault(subject_id, {"id": subject_id, "name": subject_name})

        for curriculum in class_entry.get("curriculumInfoList") or []:
            if not isinstance(curriculum, dict):
                continue
            curriculum_id = _coerce_int(curriculum.get("id"))
            if curriculum_id is not None and curriculum_id not in row["_curriculum_ids"]:
                row["_curriculum_ids"].append(curriculum_id)
            _append_unique_text(row["img_url_list"], curriculum.get("img_url"))

        for curriculum_id in (
            _coerce_int(value)
            for value in (class_entry.get("curriculumIdList") or class_entry.get("curriculum_id_list") or [])
        ):
            if curriculum_id is not None and curriculum_id not in row["_curriculum_ids"]:
                row["_curriculum_ids"].append(curriculum_id)

    for plan in store.list_teaching_plans():
        if not isinstance(plan, dict):
            continue
        class_info = plan.get("classInfo") or {}
        class_id = _coerce_int((class_info or {}).get("id") or plan.get("curriculum_class_id"))
        if class_id is None:
            continue
        if class_id in deleted_class_ids:
            continue

        row = grouped_rows.setdefault(
            class_id,
            {
                "id": class_id,
                "name": (class_info.get("name") if isinstance(class_info, dict) else "") or plan.get("className") or f"Class {class_id}",
                "img_url_list": [],
                "teachingPlanLessonImgUrl": [],
                "subjectNameList": [],
                "tchPlanNum": 0,
                "curriculumNum": 0,
                "curriculum_class_type": (class_info.get("curriculum_class_type") if isinstance(class_info, dict) else None) or 1,
                "week_json": (class_info.get("week_json") if isinstance(class_info, dict) else None) or [],
                "week_str": (class_info.get("week_str") if isinstance(class_info, dict) else None) or "",
                "time_str": (class_info.get("time_str") if isinstance(class_info, dict) else None) or "",
                "teaching_type": (class_info.get("teaching_type") if isinstance(class_info, dict) else None) or plan.get("teaching_type") or 1,
                "end_class_state": (class_info.get("end_class_state") if isinstance(class_info, dict) else None),
                "educational_institution_campus_id": (
                    (class_info.get("educational_institution_campus_id") if isinstance(class_info, dict) else None)
                    or plan.get("educational_institution_campus_id")
                    or _teacher_primary_campus_id(store)
                    or 0
                ),
                "campusName": plan.get("campusName") or _teacher_primary_campus_name(store),
                "_subject_names": [],
                "_subject_ids": [],
                "_curriculum_ids": [],
            },
        )

        row["tchPlanNum"] += 1
        curriculum_id = _coerce_int(plan.get("curriculum_id"))
        if curriculum_id is not None and curriculum_id not in row["_curriculum_ids"]:
            row["_curriculum_ids"].append(curriculum_id)
        subject_id = _coerce_int(plan.get("subject_id"))
        if subject_id is not None and subject_id not in row["_subject_ids"]:
            row["_subject_ids"].append(subject_id)

        if isinstance(class_info, dict):
            for subject in class_info.get("subjectInfoList") or []:
                if not isinstance(subject, dict):
                    continue
                info_subject_id = _coerce_int(subject.get("id"))
                info_subject_name = subject.get("name") or subject_name_map.get(info_subject_id or -1)
                if info_subject_id is not None and info_subject_id not in row["_subject_ids"]:
                    row["_subject_ids"].append(info_subject_id)
                if info_subject_name:
                    _append_unique_text(row["_subject_names"], info_subject_name)
                    if info_subject_id is not None:
                        user_subjects[info_subject_id] = {"id": info_subject_id, "name": str(info_subject_name)}

            if class_info.get("curriculum_class_type") not in (None, ""):
                row["curriculum_class_type"] = class_info["curriculum_class_type"]
            if class_info.get("week_json") not in (None, ""):
                row["week_json"] = class_info["week_json"] or []
            if class_info.get("week_str") not in (None, ""):
                row["week_str"] = class_info["week_str"] or ""
            if class_info.get("time_str") not in (None, ""):
                row["time_str"] = class_info["time_str"] or ""
            if class_info.get("teaching_type") not in (None, ""):
                row["teaching_type"] = class_info["teaching_type"]
            if class_info.get("end_class_state") not in (None, ""):
                row["end_class_state"] = class_info["end_class_state"]

            for curriculum in class_info.get("curriculumInfoList") or []:
                if not isinstance(curriculum, dict):
                    continue
                _append_unique_text(row["img_url_list"], curriculum.get("img_url"))

        if subject_id is not None:
            subject_name = subject_name_map.get(subject_id)
            if subject_name:
                _append_unique_text(row["_subject_names"], subject_name)
                user_subjects.setdefault(subject_id, {"id": subject_id, "name": subject_name})

        lesson_info = plan.get("lessionInfo") or {}
        if isinstance(lesson_info, dict):
            _append_unique_text(row["img_url_list"], lesson_info.get("img_url"))

        material = materials_by_id.get(_coerce_int(plan.get("curriculum_meterial_id")) or -1)
        if isinstance(material, dict):
            _append_unique_text(row["img_url_list"], material.get("img_url"))

    rows: list[dict[str, Any]] = []
    for row in grouped_rows.values():
        subject_names = row.pop("_subject_names")
        subject_ids = row.pop("_subject_ids")
        curriculum_ids = row.pop("_curriculum_ids")
        row["subjectNameList"] = subject_names
        row["subjectIdList"] = subject_ids
        row["subject_id_list"] = _json_deep_copy(subject_ids)
        row["curriculumIdList"] = curriculum_ids
        row["curriculum_id_list"] = _json_deep_copy(curriculum_ids)
        row["curriculumNum"] = len(curriculum_ids)
        if not row["img_url_list"]:
            row["img_url_list"] = [default_img_url]
        row["teachingPlanLessonImgUrl"] = _json_deep_copy(row["img_url_list"])
        if not isinstance(row.get("week_json"), list):
            row["week_json"] = []

        if subject_id_filter and subject_id_filter not in {str(subject_id) for subject_id in row["subjectIdList"]}:
            continue
        if teaching_type_filter and str(row.get("teaching_type") or "") != teaching_type_filter:
            continue
        if name_filter and name_filter not in str(row.get("name") or "").lower():
            continue
        if course_week_filter and course_week_filter not in {str(item) for item in row.get("week_json") or []}:
            continue
        if course_time_filter and course_time_filter not in str(row.get("time_str") or "").lower():
            continue
        rows.append(row)

    if end_class_state_filter and any(str(row.get("end_class_state")) == end_class_state_filter for row in rows):
        rows = [row for row in rows if str(row.get("end_class_state")) == end_class_state_filter]

    rows.sort(key=lambda row: (-int(row.get("tchPlanNum") or 0), str(row.get("name") or "")))
    user_subject_list = sorted(user_subjects.values(), key=lambda subject: subject["id"])
    return rows, user_subject_list


def _build_class_list_row_from_teacher_row(
    row: dict[str, Any],
    *,
    student_total_num: int = 0,
    sign_num: int | None = None,
) -> dict[str, Any]:
    normalized = _json_deep_copy(row)
    subject_id_list = [
        subject_id
        for subject_id in (_coerce_int(value) for value in (normalized.get("subjectIdList") or normalized.get("subject_id_list") or []))
        if subject_id is not None
    ]
    curriculum_id_list = [
        curriculum_id
        for curriculum_id in (
            _coerce_int(value)
            for value in (
                normalized.get("curriculum_id_list")
                or normalized.get("curriculumIdList")
                or normalized.get("curriculumIdArr")
                or []
            )
        )
        if curriculum_id is not None
    ]
    normalized["subjectIdList"] = subject_id_list
    normalized["subject_id_list"] = subject_id_list
    normalized["curriculum_id_list"] = curriculum_id_list
    normalized["curriculumIdList"] = curriculum_id_list
    normalized["student_total_num"] = max(_coerce_int(normalized.get("student_total_num") or normalized.get("stuNum")) or 0, student_total_num)
    normalized["stuNum"] = normalized["student_total_num"]
    normalized["curriculumNum"] = max(
        _coerce_int(normalized.get("curriculumNum")) or 0,
        len(curriculum_id_list),
    )
    normalized["signNum"] = max(_coerce_int(normalized.get("signNum")) or 0, sign_num or 0)
    normalized.setdefault("classXmGoodsArr", normalized.get("classXmGoodsArr") or [])
    return normalized


def _build_class_info_for_detail_page(store: MirrorStore, class_id: int | None, seed: dict[str, Any] | None = None) -> dict[str, Any]:
    base = _json_deep_copy(seed or {})
    teacher_rows, _ = _build_teacher_class_rows(store, _synthetic_request())
    teacher_row = next(
        (
            row
            for row in teacher_rows
            if isinstance(row, dict) and _coerce_int(row.get("id")) == class_id
        ),
        None,
    )
    stored_class = next(
        (
            row
            for row in store.list_classes()
            if isinstance(row, dict) and _coerce_int(row.get("id")) == class_id
        ),
        None,
    )
    class_row = _build_class_list_row_from_teacher_row(
        {
            **(_json_deep_copy(teacher_row) if isinstance(teacher_row, dict) else {}),
            **(_json_deep_copy(stored_class) if isinstance(stored_class, dict) else {}),
            **base,
        }
    )

    curriculum_info_map = store._curriculum_info_map()
    materials_by_curriculum = _curriculum_materials_by_curriculum(store)
    curriculum_list: list[dict[str, Any]] = []
    for curriculum_id in (
        _coerce_int(value)
        for value in (
            class_row.get("curriculumIdList")
            or class_row.get("curriculum_id_list")
            or class_row.get("curriculumIdArr")
            or []
        )
    ):
        if curriculum_id is None:
            continue
        curriculum_info = _json_deep_copy(curriculum_info_map.get(curriculum_id) or {})
        if not curriculum_info:
            continue
        related_materials = materials_by_curriculum.get(curriculum_id) or []
        img_url = curriculum_info.get("img_url") or ""
        if not img_url:
            for material in related_materials:
                if material.get("img_url"):
                    img_url = material.get("img_url")
                    break
        curriculum_list.append(
            {
                **curriculum_info,
                "id": curriculum_id,
                "title": curriculum_info.get("title") or curriculum_info.get("name") or f"璇剧▼ {curriculum_id}",
                "curriculum_desc": curriculum_info.get("curriculum_desc") or curriculum_info.get("desc") or "",
                "img_url": img_url,
            }
        )

    if not curriculum_list:
        for item in base.get("curriculumList") or []:
            if isinstance(item, dict):
                curriculum_list.append(_json_deep_copy(item))

    class_row["curriculumList"] = curriculum_list
    class_row.setdefault("curriculumInfoList", base.get("curriculumInfoList") or [])
    class_row.setdefault("subjectInfoList", base.get("subjectInfoList") or [])
    class_row.setdefault("curriculum_class_type", _coerce_int(class_row.get("curriculum_class_type")) or 1)
    class_row.setdefault("is_full", False)
    class_row.setdefault("semester", base.get("semester") or "")
    return class_row


def _flatten_class_student_detail_row(row: dict[str, Any]) -> dict[str, Any]:
    student_info = row.get("studentInfo") if isinstance(row.get("studentInfo"), dict) else {}
    nested_user_info = (
        student_info.get("studentUserInfo")
        if isinstance(student_info.get("studentUserInfo"), dict)
        else student_info.get("student_user_info")
        if isinstance(student_info.get("student_user_info"), dict)
        else {}
    )
    flattened = _json_deep_copy(row)
    flattened["stuId"] = _coerce_int(row.get("student_user_id") or row.get("id") or student_info.get("id")) or 0
    flattened["account"] = student_info.get("name") or flattened.get("name") or ""
    flattened["starNum"] = _coerce_int(student_info.get("wallet")) or _coerce_int(flattened.get("starNum")) or 0
    flattened["ojAnalysisAuth"] = bool(student_info.get("oj_analysis_auth"))
    flattened["ojAuth"] = bool(student_info.get("oj_auth"))
    flattened["pAuth"] = bool(student_info.get("p_auth"))
    flattened["stuNoteAuth"] = bool(student_info.get("stu_note_auth"))
    flattened["testAuth"] = bool(student_info.get("test_auth"))
    flattened["zoneAuth"] = bool(student_info.get("zone_auth"))
    flattened["ojTestcaseAuth"] = bool(student_info.get("oj_testcase_auth"))
    flattened["eduCampusId"] = _coerce_int(
        student_info.get("educational_institution_campus_id") or flattened.get("educational_institution_campus_id")
    ) or 0
    flattened["stuName"] = nested_user_info.get("realname") or student_info.get("realname") or ""
    flattened["sex"] = nested_user_info.get("sex") or student_info.get("sex") or ""
    flattened["kinship"] = nested_user_info.get("parent_a") or ""
    flattened["phoneNum"] = nested_user_info.get("parent_a_phone_num") or student_info.get("phone_num") or ""
    flattened["createdTime"] = row.get("in_class_date") or row.get("created_time") or ""
    return flattened


def _build_classes_list_content(store: MirrorStore, request: Request) -> dict[str, Any]:
    subject_id_filter = _first_query_value(request, "subject_id")
    teaching_type_filter = _first_query_value(request, "teaching_type")
    lecturer_id_filter = _first_query_value(request, "lecturer_id")
    curriculum_id_filter = _first_query_value(request, "curriculum_id")
    class_name_filter = (_first_query_value(request, "className") or "").strip().lower()
    curriculum_class_type_filter = _first_query_value(request, "curriculum_class_type")
    end_class_state_filter = _first_query_value(request, "end_class_state")

    plan_rows = _build_teacher_teaching_plan_rows(store, request)
    plan_count_by_class: dict[int, int] = {}
    signed_count_by_class: dict[int, int] = {}
    for plan in plan_rows:
        if not isinstance(plan, dict):
            continue
        class_info = plan.get("classInfo") if isinstance(plan.get("classInfo"), dict) else {}
        class_id = _coerce_int(class_info.get("id") or plan.get("curriculum_class_id"))
        if class_id is None:
            continue
        plan_count_by_class[class_id] = plan_count_by_class.get(class_id, 0) + 1
        if _coerce_int(plan.get("sign_state")) == 1:
            signed_count_by_class[class_id] = signed_count_by_class.get(class_id, 0) + 1

    stored_rows_by_id: dict[int, dict[str, Any]] = {}
    for entry in store.list_classes():
        if not isinstance(entry, dict):
            continue
        row = _json_deep_copy(entry)
        class_id = _coerce_int(row.get("id"))
        if class_id is None:
            continue
        stored_rows_by_id[class_id] = row

    teacher_rows, _ = _build_teacher_class_rows(store, request)
    merged_rows_by_id: dict[int, dict[str, Any]] = {}
    for teacher_row in teacher_rows:
        if not isinstance(teacher_row, dict):
            continue
        class_id = _coerce_int(teacher_row.get("id"))
        if class_id is None:
            continue
        class_student_payload = store.get_class_student_payload(class_id) or {}
        student_rows = class_student_payload.get("studentList") if isinstance(class_student_payload, dict) else []
        student_total_num = len(student_rows) if isinstance(student_rows, list) else 0
        merged_rows_by_id[class_id] = _build_class_list_row_from_teacher_row(
            teacher_row,
            student_total_num=student_total_num,
            sign_num=signed_count_by_class.get(class_id, 0),
        )

    rows: list[dict[str, Any]] = []
    for class_id, row in stored_rows_by_id.items():
        merged_rows_by_id[class_id] = {**merged_rows_by_id.get(class_id, {}), **row}

    for class_id, row in merged_rows_by_id.items():
        if not isinstance(row, dict):
            continue
        row = _build_class_list_row_from_teacher_row(
            row,
            student_total_num=_coerce_int(row.get("student_total_num") or row.get("stuNum")) or 0,
            sign_num=signed_count_by_class.get(class_id, 0),
        )

        subject_id_list = [
            subject_id
            for subject_id in (
                _coerce_int(value)
                for value in (row.get("subject_id_list") or row.get("subjectIdList") or [])
            )
            if subject_id is not None
        ]
        curriculum_id_list = [
            curriculum_id
            for curriculum_id in (
                _coerce_int(value)
                for value in (row.get("curriculum_id_list") or row.get("curriculumIdList") or [])
            )
            if curriculum_id is not None
        ]

        if subject_id_filter and subject_id_filter not in {str(value) for value in subject_id_list}:
            continue
        if curriculum_id_filter and curriculum_id_filter not in {str(value) for value in curriculum_id_list}:
            continue
        if teaching_type_filter and str(row.get("teaching_type") or "") != teaching_type_filter:
            continue
        if lecturer_id_filter and str(row.get("lecturer_id") or "") != lecturer_id_filter:
            continue
        if curriculum_class_type_filter and str(row.get("curriculum_class_type") or "") != curriculum_class_type_filter:
            continue
        if end_class_state_filter:
            row_end_class_state = _coerce_int(row.get("end_class_state"))
            requested_end_class_state = _coerce_int(end_class_state_filter)
            if (
                row_end_class_state is not None
                and requested_end_class_state is not None
                and row_end_class_state != requested_end_class_state
            ):
                continue
        if class_name_filter and class_name_filter not in str(row.get("name") or "").lower():
            continue

        row["subject_id_list"] = subject_id_list
        row["subjectIdList"] = subject_id_list
        row["curriculum_id_list"] = curriculum_id_list
        row["curriculumIdList"] = curriculum_id_list
        class_student_payload = store.get_class_student_payload(class_id) or {}
        student_rows = class_student_payload.get("studentList") if isinstance(class_student_payload, dict) else []
        student_total_num = len(student_rows) if isinstance(student_rows, list) else 0
        row["student_total_num"] = max(_coerce_int(row.get("student_total_num") or row.get("stuNum")) or 0, student_total_num)
        row["stuNum"] = row["student_total_num"]
        row["curriculumNum"] = max(
            _coerce_int(row.get("curriculumNum")) or 0,
            len(curriculum_id_list),
            plan_count_by_class.get(class_id, 0),
        )
        row["signNum"] = max(_coerce_int(row.get("signNum")) or 0, signed_count_by_class.get(class_id, 0))
        row.setdefault("classXmGoodsArr", row.get("classXmGoodsArr") or [])
        rows.append(row)

    page_no, page_size, start = _page_window(request)
    page_rows = rows[start:start + page_size]
    return {
        "class_list": page_rows,
        "classList": page_rows,
        "list": page_rows,
        "rows": page_rows,
        "total": len(rows),
        "page_no": page_no,
        "page_size": page_size,
    }


def _teaching_plan_state_label(plan: dict[str, Any]) -> str:
    raw_state = plan.get("teachingPlanState")
    if raw_state not in (None, ""):
        return str(raw_state)
    sign_state = _coerce_int(plan.get("sign_state") or plan.get("sign_state_new"))
    if sign_state == 1:
        return "Started"
    return "Planned"


def _build_teacher_teaching_plan_rows(store: MirrorStore, request: Request) -> list[dict[str, Any]]:
    class_id_filter = _first_query_value(request, "class_id")
    sign_state_filter = _first_query_value(request, "sign_state")
    title_filter = (_first_query_value(request, "title") or "").strip().lower()
    lecturer_id_filter = _first_query_value(request, "lecturer_id")
    campus_id_filter = _first_query_value(request, "campus_id")

    materials_by_id: dict[int, dict[str, Any]] = {}
    for material in store.list_curriculum_materials():
        if not isinstance(material, dict):
            continue
        material_id = _coerce_int(material.get("id"))
        if material_id is not None:
            materials_by_id[material_id] = material

    subject_name_map = _teacher_subject_name_map(store)
    teacher_user = _hydrate_teacher_user_info(store, _teacher_user_info(store))
    default_lecturer_name = (
        teacher_user.get("realName")
        or teacher_user.get("realname")
        or teacher_user.get("name")
        or teacher_user.get("username")
        or teacher_user.get("userRealname")
        or ""
    )

    rows: list[dict[str, Any]] = []
    for plan in store.list_teaching_plans():
        if not isinstance(plan, dict):
            continue

        class_info = plan.get("classInfo") if isinstance(plan.get("classInfo"), dict) else {}
        class_id = _coerce_int(class_info.get("id") or plan.get("curriculum_class_id"))
        lecturer_id = _coerce_int(plan.get("lecturer_id") or class_info.get("lecturer_id"))
        campus_id = _coerce_int(
            plan.get("educational_institution_campus_id")
            or class_info.get("educational_institution_campus_id")
            or _teacher_primary_campus_id(store)
        )
        material = materials_by_id.get(_coerce_int(plan.get("curriculum_meterial_id")) or -1)
        lesson_info = plan.get("lessionInfo") if isinstance(plan.get("lessionInfo"), dict) else {}
        class_name = str(class_info.get("name") or plan.get("className") or f"Class {class_id or ''}").strip()
        lesson_title = str(
            plan.get("custom_lesson_title")
            or lesson_info.get("title")
            or (material or {}).get("title")
            or plan.get("title")
            or ""
        ).strip()
        subject_id = _coerce_int(plan.get("subject_id"))
        subject_name = subject_name_map.get(subject_id or -1) or ""
        lecturer_name = (
            plan.get("lecturerName")
            or class_info.get("lectureName")
            or class_info.get("lecturerName")
            or default_lecturer_name
        )

        if class_id_filter and str(class_id or "") != class_id_filter:
            continue
        if lecturer_id_filter and str(lecturer_id or "") != lecturer_id_filter:
            continue
        if campus_id_filter and str(campus_id or "") != campus_id_filter:
            continue
        if sign_state_filter:
            sign_candidates = {
                str(value)
                for value in (plan.get("sign_state"), plan.get("sign_state_new"))
                if value not in (None, "")
            }
            if sign_candidates and sign_state_filter not in sign_candidates:
                continue
        if title_filter:
            haystack = " ".join(
                part for part in (lesson_title, class_name, subject_name, str(plan.get("title") or "")) if part
            ).lower()
            if title_filter not in haystack:
                continue

        row = _json_deep_copy(plan)
        row["classInfo"] = _json_deep_copy(class_info)
        row["lessionInfo"] = _json_deep_copy(lesson_info)
        row.setdefault("curriculum_class_id", class_id)
        row.setdefault("className", class_name)
        row.setdefault("lecturer_id", lecturer_id or 0)
        row.setdefault("lecturerName", lecturer_name)
        row.setdefault("subjectName", subject_name)
        row.setdefault("campusName", _teacher_primary_campus_name(store))
        row.setdefault("educational_institution_campus_id", campus_id or 0)
        row["teachingPlanState"] = _teaching_plan_state_label(row)
        if not row["lessionInfo"] and material is not None:
            row["lessionInfo"] = {
                "id": material.get("id"),
                "title": material.get("title") or "",
                "img_url": material.get("img_url") or "",
                "ppt_url": material.get("ppt_url") or "",
            }
        if material is not None:
            row.setdefault("curriculum_id", material.get("curriculum_id") or row.get("curriculum_id"))
            row.setdefault("subject_id", material.get("subject_id") or row.get("subject_id"))
            row.setdefault("curriculum_meterial_id", material.get("id") or row.get("curriculum_meterial_id"))
        rows.append(row)

    rows.sort(
        key=lambda row: (
            str(row.get("start_class_date") or row.get("class_date") or ""),
            _coerce_int(row.get("sort_num")) or 0,
            _coerce_int(row.get("id")) or 0,
        )
    )
    return rows


def _build_teacher_evaluate_student_rows(store: MirrorStore, request: Request) -> list[dict[str, Any]]:
    page_students = store.list_local_students()
    teaching_plan_id = _extract_teaching_plan_id_from_request(request)
    selected_plan = None
    if teaching_plan_id is not None:
        for plan in store.list_teaching_plans():
            if _coerce_int((plan or {}).get("id")) == teaching_plan_id:
                selected_plan = plan
                break
    if selected_plan is None:
        plans = store.list_teaching_plans()
        selected_plan = plans[0] if plans else None

    rows: list[dict[str, Any]] = []
    for index, student in enumerate(page_students, start=1):
        student_id = _coerce_int(student.get("id")) or index
        row = {
            "id": student_id,
            "stuTchPlanId": student_id,
            "stu_tch_plan_id": student_id,
            "teachingPlanId": _coerce_int((selected_plan or {}).get("id")) or 0,
            "student_user_id": student_id,
            "stu_user_id": student_id,
            "sign_state": 0,
            "is_evaluate": False,
            "stuInfo": {
                "id": student_id,
                "name": student.get("name") or "",
                "realName": _student_display_name(student, default_id=student_id),
                "headimgUrl": student.get("headimg_url") or "",
                "headimg_url": student.get("headimg_url") or "",
            },
            "tchPlanInfo": _json_deep_copy(selected_plan or {}),
        }
        rows.append(row)
    return rows


def _build_teacher_classroom_student_plan_rows(store: MirrorStore, request: Request) -> dict[str, Any]:
    selected_plan = _select_teaching_plan(store, request) or {}
    selected_plan_id = _coerce_int(selected_plan.get("id")) or 0
    requested_teaching_plan_id = _extract_teaching_plan_id_from_request(request) or 0
    teaching_plan_id = requested_teaching_plan_id or selected_plan_id
    class_info = selected_plan.get("classInfo") if isinstance(selected_plan.get("classInfo"), dict) else {}
    class_id = _coerce_int(class_info.get("id") or selected_plan.get("curriculum_class_id"))
    teacher_info = _teacher_user_info(store)
    default_lecturer_name = str(
        selected_plan.get("lecturerName")
        or class_info.get("lectureName")
        or class_info.get("lecturerName")
        or teacher_info.get("realName")
        or teacher_info.get("realname")
        or teacher_info.get("name")
        or teacher_info.get("username")
        or ""
    ).strip()
    school_info = _teacher_school_info(store)
    edu_id = _coerce_int(selected_plan.get("educational_institution_id") or school_info.get("id")) or 0
    edu_campus_id = _coerce_int(
        selected_plan.get("educational_institution_campus_id")
        or class_info.get("educational_institution_campus_id")
        or school_info.get("eduCampusId")
        or school_info.get("educationalInstitutionCampusId")
        or _teacher_primary_campus_id(store)
    ) or 0
    subject_id = _coerce_int(selected_plan.get("subject_id")) or 0
    subject_snapshot = _teacher_subject_snapshot(store, str(subject_id) if subject_id else None)
    material = _resolve_teacher_curriculum_material(store, request) or _default_teacher_curriculum_material(store)
    lesson_info = selected_plan.get("lessionInfo") if isinstance(selected_plan.get("lessionInfo"), dict) else {}
    lesson_title = str(
        lesson_info.get("title")
        or selected_plan.get("title")
        or (material or {}).get("title")
        or ""
    ).strip()
    sign_date = str(
        selected_plan.get("class_date")
        or selected_plan.get("start_class_date")
        or selected_plan.get("sign_date")
        or ""
    ).strip()
    sign_end_date = str(
        selected_plan.get("end_class_date")
        or selected_plan.get("sign_end_date")
        or sign_date
    ).strip()
    cover_url = _material_asset_url(
        store,
        material,
        (
            "img_url",
            "other_meterial_url",
            "ppt_url",
            "stu_note_url",
            "video_url",
            "teach_template_url",
            "home_template_url",
        ),
    ) or str(lesson_info.get("img_url") or "")
    template_info = _teaching_plan_template_info(
        store,
        request,
        teaching_plan_id=teaching_plan_id or selected_plan_id,
    )
    class_work_url = str(
        template_info.get("classWorkUrl")
        or template_info.get("exampleWorkUrl")
        or _material_asset_url(store, material, ("teach_template_url", "exampal_work_url", "home_template_url"))
        or (material or {}).get("teach_template_url")
        or (material or {}).get("exampal_work_url")
        or (material or {}).get("home_template_url")
        or (material or {}).get("ppt_url")
        or (material or {}).get("video_url")
        or cover_url
        or ""
    ).strip()
    homework_work_url = str(
        template_info.get("homeworkWorkUrl")
        or _material_asset_url(store, material, ("home_template_url", "teach_template_url", "exampal_work_url"))
        or (material or {}).get("home_template_url")
        or (material or {}).get("teach_template_url")
        or (material or {}).get("exampal_work_url")
        or (material or {}).get("ppt_url")
        or (material or {}).get("video_url")
        or cover_url
        or ""
    ).strip()

    membership_ids: list[int] = []
    seen_student_ids: set[int] = set()
    if selected_plan_id:
        for relation in store.list_local_teaching_plan_students(selected_plan_id):
            if not isinstance(relation, dict):
                continue
            student_id = _coerce_int(relation.get("student_user_id"))
            if student_id is not None and student_id not in seen_student_ids:
                membership_ids.append(student_id)
                seen_student_ids.add(student_id)
    if class_id is not None:
        class_payload = store.get_class_student_payload(class_id)
        if isinstance(class_payload, dict):
            class_rows = class_payload.get("studentList") or []
            if isinstance(class_rows, list):
                for relation in class_rows:
                    if not isinstance(relation, dict):
                        continue
                    student_id = _coerce_int(relation.get("student_user_id"))
                    if student_id is None:
                        student_id = _coerce_int(((relation.get("studentInfo") or {}).get("id")))
                    if student_id is not None and student_id not in seen_student_ids:
                        membership_ids.append(student_id)
                        seen_student_ids.add(student_id)

    student_rows = []
    all_students = store.list_local_students()
    if membership_ids:
        students_by_id: dict[int, dict[str, Any]] = {}
        for student in all_students:
            if not isinstance(student, dict):
                continue
            student_id = _coerce_int(student.get("id"))
            if student_id is not None:
                students_by_id[student_id] = student
        for student_id in membership_ids:
            student = students_by_id.get(student_id)
            if isinstance(student, dict):
                student_rows.append(student)
    else:
        student_rows = [student for student in all_students if isinstance(student, dict)]

    rows: list[dict[str, Any]] = []
    for index, student in enumerate(student_rows, start=1):
        student_id = _coerce_int(student.get("id")) or index
        student_info = _build_local_student_entry(student, store)
        student_name = _student_display_name(student, default_id=student_id)
        account_name = str(student.get("name") or f"mirror-student-{student_id}")
        headimg_url = str(
            student.get("headimg_url")
            or ((student_info.get("studentUserInfo") or {}).get("headimg_url"))
            or DEFAULT_HOMEPAGE_AVATAR_URL
        )
        row_id = teaching_plan_id * 1000 + student_id if teaching_plan_id else student_id
        class_work_state = bool(class_work_url)
        home_work_state = bool(homework_work_url)
        class_work_info = {
            "id": row_id,
            "workId": row_id,
            "stu_tch_plan_id": row_id,
            "stuTchPlanId": row_id,
            "title": lesson_title,
            "name": student_name,
            "work_url": class_work_url,
            "workUrl": class_work_url,
            "covers": cover_url,
            "coverUrl": cover_url,
            "work_type": 1,
            "workType": "1",
            "subject_id": subject_id,
            "subject_code": subject_snapshot.get("subjectCode") or str(subject_id or ""),
            "subjectCode": subject_snapshot.get("subjectCode") or str(subject_id or ""),
            "student_user_id": student_id,
            "stu_user_id": student_id,
            "stuUserId": student_id,
            "educational_institution_id": edu_id,
            "eduId": edu_id,
            "educational_institution_campus_id": edu_campus_id,
            "eduCampusId": edu_campus_id,
            "markpoint": 0,
            "remark": "",
            "is_good": index == 1,
            "is_only": True,
            "headimg_url": headimg_url,
            "headImgUrl": headimg_url,
        }
        home_work_info = {
            "id": row_id,
            "workId": row_id,
            "stu_tch_plan_id": row_id,
            "stuTchPlanId": row_id,
            "title": lesson_title,
            "name": student_name,
            "work_url": homework_work_url,
            "workUrl": homework_work_url,
            "covers": cover_url,
            "coverUrl": cover_url,
            "work_type": 2,
            "workType": "2",
            "subject_id": subject_id,
            "subject_code": subject_snapshot.get("subjectCode") or str(subject_id or ""),
            "subjectCode": subject_snapshot.get("subjectCode") or str(subject_id or ""),
            "student_user_id": student_id,
            "stu_user_id": student_id,
            "stuUserId": student_id,
            "educational_institution_id": edu_id,
            "eduId": edu_id,
            "educational_institution_campus_id": edu_campus_id,
            "eduCampusId": edu_campus_id,
            "markpoint": 0,
            "remark": "",
            "is_good": index == 1,
            "is_only": True,
            "headimg_url": headimg_url,
            "headImgUrl": headimg_url,
        }

        row = {
            "id": row_id,
            "stuTchPlanId": row_id,
            "stu_tch_plan_id": row_id,
            "student_user_id": student_id,
            "stu_user_id": student_id,
            "stuUserId": student_id,
            "teaching_plan_id": teaching_plan_id,
            "teachingPlanId": teaching_plan_id,
            "tchPlanId": teaching_plan_id,
            "educational_institution_id": edu_id,
            "eduId": edu_id,
            "educational_institution_campus_id": edu_campus_id,
            "eduCampusId": edu_campus_id,
            "subject_id": subject_id,
            "subject_code": subject_snapshot.get("subjectCode") or str(subject_id or ""),
            "subjectCode": subject_snapshot.get("subjectCode") or str(subject_id or ""),
            "subject_name": subject_snapshot.get("subjectName") or "",
            "subjectName": subject_snapshot.get("subjectName") or "",
            "name": student_name,
            "username": account_name,
            "realName": student_name,
            "headimg_url": headimg_url,
            "headImgUrl": headimg_url,
            "className": str(class_info.get("name") or selected_plan.get("className") or ""),
            "campusName": _teacher_primary_campus_name(store),
            "lecturerName": default_lecturer_name,
            "sign_state": _coerce_int(selected_plan.get("sign_state") or selected_plan.get("signState")) or 0,
            "signState": _coerce_int(selected_plan.get("sign_state") or selected_plan.get("signState")) or 0,
            "sign_date": sign_date,
            "sign_end_date": sign_end_date,
            "signDate": sign_date,
            "signEndDate": sign_end_date,
            "classWorkState": class_work_state,
            "homeWorkState": home_work_state,
            "xmGoodsList": _build_local_xm_goods_rows(student, store=store),
            "classWorkInfo": class_work_info,
            "homeWorkInfo": home_work_info,
            "studentInfo": student_info,
            "stuInfo": {
                "id": student_id,
                "name": student_name,
                "realName": student_name,
                "headimgUrl": headimg_url,
                "headimg_url": headimg_url,
            },
            "tchPlanInfo": {
                **_json_deep_copy(selected_plan),
                "id": teaching_plan_id,
                "teachingPlanId": teaching_plan_id,
                "tchPlanId": teaching_plan_id,
            },
            "lessionInfo": _json_deep_copy(lesson_info),
            "title": lesson_title,
            "covers": cover_url,
        }
        rows.append(row)

    page_no, page_size, start = _page_window(request)
    page_rows = rows[start:start + page_size]
    return {
        "stuTchPlanList": page_rows,
        "tchPlanList": page_rows,
        "list": page_rows,
        "rows": page_rows,
        "total": len(rows),
        "page_no": page_no,
        "page_size": page_size,
        "pageNum": page_no,
        "pageSize": page_size,
    }


def _select_teaching_plan(store: MirrorStore, request: Request) -> dict[str, Any] | None:
    teaching_plan_id = _extract_teaching_plan_id_from_request(request)
    plans = store.list_teaching_plans()
    if teaching_plan_id is not None:
        for plan in plans:
            if _coerce_int((plan or {}).get("id")) == teaching_plan_id:
                return plan
    return plans[0] if plans else None


def _find_teaching_plan(store: MirrorStore, teaching_plan_id: Any) -> dict[str, Any] | None:
    normalized_teaching_plan_id = _coerce_int(teaching_plan_id)
    if normalized_teaching_plan_id is None:
        return None
    for plan in store.list_teaching_plans():
        if _coerce_int((plan or {}).get("id")) == normalized_teaching_plan_id:
            return plan
    return None


def _teaching_plan_template_info(
    store: MirrorStore,
    request: Request,
    *,
    curr_mat_id: Any = None,
    teaching_plan_id: Any = None,
) -> dict[str, Any]:
    normalized_teaching_plan_id = _coerce_int(teaching_plan_id)
    overlay = store.get_teaching_plan_overlay(normalized_teaching_plan_id) if normalized_teaching_plan_id is not None else None
    material = None
    normalized_curr_mat_id = _coerce_int(curr_mat_id)
    if normalized_curr_mat_id is not None:
        material = store.find_curriculum_material(normalized_curr_mat_id)
    material = (
        material
        or _resolve_teacher_curriculum_material(store, request)
        or _default_teacher_curriculum_material(store)
        or (store.list_curriculum_materials()[0] if store.list_curriculum_materials() else {})
    )
    default_class_work_url = _material_asset_url(
        store,
        material,
        (
            "teach_template_url",
            "exampal_work_url",
            "home_template_url",
            "ppt_url",
            "video_url",
            "stu_note_url",
            "other_meterial_url",
            "img_url",
        ),
    )
    default_example_work_url = _material_asset_url(
        store,
        material,
        (
            "exampal_work_url",
            "teach_template_url",
            "home_template_url",
            "ppt_url",
            "video_url",
            "stu_note_url",
            "other_meterial_url",
            "img_url",
        ),
    )
    default_homework_work_url = _material_asset_url(
        store,
        material,
        (
            "home_template_url",
            "teach_template_url",
            "exampal_work_url",
            "ppt_url",
            "video_url",
            "stu_note_url",
            "other_meterial_url",
            "img_url",
        ),
    )
    return {
        "id": normalized_teaching_plan_id or 0,
        "tchPlanId": normalized_teaching_plan_id or 0,
        "teachingPlanId": normalized_teaching_plan_id or 0,
        "classWorkUrl": (overlay or {}).get("class_work_url") or default_class_work_url or "",
        "exampleWorkUrl": (overlay or {}).get("example_work_url") or default_example_work_url or "",
        "homeworkWorkUrl": (overlay or {}).get("homework_work_url") or default_homework_work_url or "",
        "sourceTchPlanId": (overlay or {}).get("source_tch_plan_id") or 0,
    }


def _coerce_float_like(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return default
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _teaching_plan_cost_lesson_hour(plan: dict[str, Any] | None) -> float:
    plan = plan if isinstance(plan, dict) else {}
    class_info = plan.get("classInfo") if isinstance(plan.get("classInfo"), dict) else {}
    for candidate in (
        plan.get("cost_lesson_hour"),
        class_info.get("cost_lesson_hour"),
        class_info.get("lesson_hour"),
        plan.get("lesson_hour"),
    ):
        if candidate not in (None, ""):
            normalized_candidate = _coerce_float_like(candidate, 0.0)
            if normalized_candidate > 0:
                return normalized_candidate
    return 1.0


def _build_teaching_plan_student_rows(store: MirrorStore, request: Request) -> dict[str, Any]:
    selected_plan = _select_teaching_plan(store, request) or {}
    class_info = _json_deep_copy(selected_plan.get("classInfo") or {})
    cost_lesson_hour = _teaching_plan_cost_lesson_hour(selected_plan)
    if "lesson_hour" not in class_info or class_info.get("lesson_hour") in (None, ""):
        class_info["lesson_hour"] = cost_lesson_hour
    if "is_cost_lesson_hour" not in class_info or class_info.get("is_cost_lesson_hour") in (None, ""):
        class_info["is_cost_lesson_hour"] = bool(selected_plan.get("is_cost_lesson_hour") or False)

    teaching_plan_info = _json_deep_copy(selected_plan)
    teaching_plan_info.setdefault("classInfo", _json_deep_copy(class_info))
    teaching_plan_info.setdefault("cost_lesson_hour", cost_lesson_hour)
    teaching_plan_info["teachingPlanState"] = _teaching_plan_state_label(teaching_plan_info)
    teaching_plan_info.setdefault("className", class_info.get("name") or selected_plan.get("className") or "")
    teaching_plan_info.setdefault("campusName", _teacher_primary_campus_name(store))
    teaching_plan_info.setdefault(
        "educational_institution_campus_id",
        class_info.get("educational_institution_campus_id")
        or selected_plan.get("educational_institution_campus_id")
        or _teacher_primary_campus_id(store)
        or 0,
    )

    selected_plan_id = _coerce_int(teaching_plan_info.get("id"))
    class_id = _coerce_int(class_info.get("id") or selected_plan.get("curriculum_class_id"))
    relation_sources: list[tuple[str, dict[str, Any]]] = []
    used_membership_source = False
    if selected_plan_id is not None and store.is_teaching_plan_student_overridden(selected_plan_id):
        used_membership_source = True
        for relation in store.list_local_teaching_plan_students(selected_plan_id):
            if isinstance(relation, dict):
                relation_sources.append(("plan", relation))
    elif class_id is not None:
        class_payload = store.get_class_student_payload(class_id)
        if isinstance(class_payload, dict):
            used_membership_source = True
            class_student_rows = class_payload.get("studentList") or []
            if isinstance(class_student_rows, list):
                for relation in class_student_rows:
                    if isinstance(relation, dict):
                        relation_sources.append(("class", relation))

    rows: list[dict[str, Any]] = []
    if used_membership_source:
        for source_kind, relation in relation_sources:
            student_id = _coerce_int(relation.get("student_user_id"))
            if student_id is None:
                student_id = _coerce_int(((relation.get("studentInfo") or {}).get("id")))
            if student_id is None:
                continue

            if source_kind == "plan":
                snapshot = store._student_snapshot_by_id(student_id)
                student_user_info = _json_deep_copy(snapshot.get("studentUserInfo") or {})
                headimg_url = str(student_user_info.get("headimg_url") or snapshot.get("headimg_url") or "").strip()
                student_info = {
                    "id": student_id,
                    "name": snapshot.get("name") or f"student-{student_id}",
                    "headimg_url": headimg_url,
                    "studentUserInfo": student_user_info,
                }
                xm_goods_id = _coerce_int(relation.get("xm_goods_id"))
                sign_state = relation.get("sign_state")
                sign_date = relation.get("sign_date")
                cost_state = relation.get("cost_state") or "1"
                relation_cost_lesson_hour = relation.get("cost_lesson_hour")
                over_lesson_hour = relation.get("over_lesson_hour") or 0
                not_come_reason = relation.get("not_come_reason") or ""
                remark = relation.get("remark") or ""
                stu_tch_plan_type = relation.get("stu_tch_plan_type") or 1
            else:
                class_student_info = relation.get("studentInfo") if isinstance(relation.get("studentInfo"), dict) else {}
                student_user_info = _json_deep_copy(class_student_info.get("studentUserInfo") or {})
                headimg_url = str(class_student_info.get("headimg_url") or student_user_info.get("headimg_url") or "").strip()
                student_info = {
                    "id": student_id,
                    "name": class_student_info.get("name") or f"student-{student_id}",
                    "headimg_url": headimg_url,
                    "studentUserInfo": student_user_info,
                }
                xm_goods_id = _coerce_int(relation.get("xm_goods_id"))
                sign_state = relation.get("sign_state")
                sign_date = relation.get("sign_date")
                cost_state = relation.get("cost_state") or "1"
                relation_cost_lesson_hour = relation.get("cost_lesson_hour")
                over_lesson_hour = relation.get("over_lesson_hour") or 0
                not_come_reason = relation.get("not_come_reason") or ""
                remark = relation.get("remark") or ""
                stu_tch_plan_type = relation.get("stu_tch_plan_type") or 1

            rows.append(
                {
                    "id": _coerce_int(relation.get("id")) or student_id,
                    "stuTchPlanId": _coerce_int(relation.get("id")) or student_id,
                    "stu_tch_plan_id": _coerce_int(relation.get("id")) or student_id,
                    "student_user_id": student_id,
                    "stu_user_id": student_id,
                    "teaching_plan_id": selected_plan_id or 0,
                    "teachingPlanId": selected_plan_id or 0,
                    "studentInfo": student_info,
                    "sign_state": sign_state,
                    "cost_state": cost_state,
                    "cost_lesson_hour": relation_cost_lesson_hour if relation_cost_lesson_hour not in (None, "") else cost_lesson_hour,
                    "over_lesson_hour": over_lesson_hour,
                    "sign_date": sign_date,
                    "not_come_reason": not_come_reason,
                    "remark": remark,
                    "stu_tch_plan_type": stu_tch_plan_type,
                    "xmGoodsList": [{"id": xm_goods_id, "student_user_id": student_id}] if xm_goods_id is not None else [],
                    "classWorkState": 0,
                    "homeWorkState": 0,
                    "evaluatereadCount": 0,
                    "evaluateCount": 0,
                }
            )
    else:
        for index, student in enumerate(store.list_local_students(), start=1):
            student_id = _coerce_int(student.get("id")) or index
            student_info = _build_local_student_entry(student, store)
            row = {
                "id": student_id,
                "stuTchPlanId": student_id,
                "stu_tch_plan_id": student_id,
                "student_user_id": student_id,
                "stu_user_id": student_id,
                "teaching_plan_id": _coerce_int(teaching_plan_info.get("id")) or 0,
                "teachingPlanId": _coerce_int(teaching_plan_info.get("id")) or 0,
                "studentInfo": student_info,
                "sign_state": None,
                "cost_state": "1",
                "cost_lesson_hour": cost_lesson_hour,
                "over_lesson_hour": 0,
                "sign_date": None,
                "not_come_reason": "",
                "remark": "",
                "stu_tch_plan_type": 1,
                "xmGoodsList": [],
                "classWorkState": 0,
                "homeWorkState": 0,
                "evaluatereadCount": 0,
                "evaluateCount": 0,
            }
            rows.append(row)

    page_no, page_size, start = _page_window(request)
    page_rows = rows[start:start + page_size]
    return {
        "curriculumClassInfo": class_info,
        "stuPlanList": page_rows,
        "tchPlanInfo": teaching_plan_info,
        "list": page_rows,
        "rows": page_rows,
        "total": len(rows),
        "page_no": page_no,
        "page_size": page_size,
    }


def _build_class_student_list_content(store: MirrorStore, request: Request) -> dict[str, Any]:
    class_id = _extract_class_id_from_request(request)
    captured_content = store.get_class_student_payload(class_id)
    if captured_content is not None:
        source_rows = captured_content.get("studentList") or []
    else:
        source_rows = []
        for index, student in enumerate(store.list_local_students(), start=1):
            student_id = _coerce_int(student.get("id")) or index
            student_info = _build_local_student_entry(student, store)
            source_rows.append(
                {
                    "id": student_id,
                    "student_user_id": student_id,
                    "curriculum_class_id": class_id or 0,
                    "xm_goods_id": None,
                    "in_class_date": student.get("created_time") or "",
                    "out_class_date": None,
                    "out_class_reason": None,
                    "is_vaild": True,
                    "created_time": student.get("created_time") or "",
                    "studentInfo": {
                        "id": student_id,
                        "name": student_info.get("name") or student.get("name") or "",
                        "headimg_url": (student_info.get("studentUserInfo") or {}).get("headimg_url") or "",
                        "studentUserInfo": _json_deep_copy(student_info.get("studentUserInfo") or {}),
                    },
                    "missStuTchPlanNum": 0,
                    "missStuTchPlanArr": [],
                }
            )

    realname_filter = (_first_query_value(request, "realname") or "").strip().lower()
    filtered_rows: list[dict[str, Any]] = []
    for row in source_rows:
        if not isinstance(row, dict):
            continue
        student_info = row.get("studentInfo") if isinstance(row.get("studentInfo"), dict) else {}
        nested_user_info = student_info.get("studentUserInfo") if isinstance(student_info.get("studentUserInfo"), dict) else {}
        if realname_filter:
            haystack = " ".join(
                part
                for part in (
                    nested_user_info.get("realname"),
                    nested_user_info.get("nickname"),
                )
                if part
            ).lower()
            if realname_filter not in haystack:
                continue
        filtered_rows.append(_json_deep_copy(row))

    page_no, page_size, start = _page_window(request)
    page_rows = filtered_rows[start:start + page_size]
    return {
        "studentList": page_rows,
        "list": page_rows,
        "rows": page_rows,
        "page_no": page_no,
        "page_size": page_size,
        "total": len(filtered_rows),
    }


def _build_teaching_plan_by_class_content(store: MirrorStore, request: Request) -> dict[str, Any]:
    class_id = _extract_class_id_from_request(request)
    captured_content = store.get_teaching_plan_by_class_payload(class_id)
    if captured_content is not None:
        source_rows = captured_content.get("teaching_plan_list") or []
    else:
        source_rows = []
        subject_name_map = _teacher_subject_name_map(store)
        student_total = (
            _parse_int_like((store.get_class_student_payload(class_id) or {}).get("total"))
            or len(store.list_local_students())
        )
        for plan in store.list_teaching_plans():
            if not isinstance(plan, dict):
                continue
            class_info = plan.get("classInfo") if isinstance(plan.get("classInfo"), dict) else {}
            plan_class_id = _coerce_int(class_info.get("id") or plan.get("curriculum_class_id"))
            if class_id is not None and plan_class_id != class_id:
                continue
            lesson_info = plan.get("lessionInfo") if isinstance(plan.get("lessionInfo"), dict) else {}
            source_rows.append(
                {
                    "id": plan.get("id"),
                    "lessionInfo": _json_deep_copy(lesson_info),
                    "subject_id": plan.get("subject_id"),
                    "subject_name": subject_name_map.get(_coerce_int(plan.get("subject_id")) or -1) or "",
                    "lecturer_id": plan.get("lecturer_id"),
                    "lecturer_name": plan.get("lecturerName") or class_info.get("lecturerName") or "",
                    "start_class_date": plan.get("start_class_date"),
                    "end_class_date": plan.get("end_class_date"),
                    "class_date": plan.get("class_date"),
                    "sign_state": plan.get("sign_state"),
                    "sign_state_new": plan.get("sign_state_new"),
                    "sign_date": plan.get("sign_date"),
                    "cost_lesson_hour": plan.get("cost_lesson_hour"),
                    "sort_num": plan.get("sort_num"),
                    "curriculum_class_id": plan_class_id or 0,
                    "educational_institution_campus_id": (
                        plan.get("educational_institution_campus_id")
                        or class_info.get("educational_institution_campus_id")
                        or _teacher_primary_campus_id(store)
                        or 0
                    ),
                    "custom_lesson_title": plan.get("custom_lesson_title") or "",
                    "custom_lesson_desc": plan.get("custom_lesson_desc"),
                    "stuTchPlanArr": [],
                    "expected_count": student_total,
                    "actual_count": 0,
                }
            )

    title_filter = (_first_query_value(request, "title") or "").strip().lower()
    sign_state_filter = (_first_query_value(request, "sign_state") or "").strip()
    filtered_rows: list[dict[str, Any]] = []
    for row in source_rows:
        if not isinstance(row, dict):
            continue
        lesson_info = row.get("lessionInfo") if isinstance(row.get("lessionInfo"), dict) else {}
        if title_filter:
            haystack = " ".join(
                part
                for part in (
                    lesson_info.get("title"),
                    row.get("custom_lesson_title"),
                    row.get("subject_name"),
                )
                if part
            ).lower()
            if title_filter not in haystack:
                continue
        if sign_state_filter:
            sign_candidates = {
                str(value)
                for value in (row.get("sign_state"), row.get("sign_state_new"))
                if value not in (None, "")
            }
            if sign_candidates and sign_state_filter not in sign_candidates:
                continue
        filtered_rows.append(_json_deep_copy(row))

    filtered_rows.sort(
        key=lambda row: (
            str(row.get("class_date") or row.get("start_class_date") or ""),
            _coerce_int(row.get("sort_num")) or 0,
            _coerce_int(row.get("id")) or 0,
        )
    )
    return {
        "teaching_plan_list": filtered_rows,
        "teachingPlanList": filtered_rows,
        "list": filtered_rows,
        "rows": filtered_rows,
    }


def _build_signed_teaching_plan_count_content(store: MirrorStore, request: Request, request_body: bytes) -> dict[str, Any]:
    submitted = _load_request_payload(request_body)
    class_id = _extract_class_id_from_request(request, submitted)
    payload = store.get_teaching_plan_by_class_payload(class_id)
    if payload is not None:
        rows = payload.get("teaching_plan_list") or []
    else:
        rows = [
            plan
            for plan in store.list_teaching_plans()
            if _coerce_int(((plan.get("classInfo") or {}).get("id")) or plan.get("curriculum_class_id")) == class_id
        ]

    signed_count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if _coerce_int(row.get("sign_state")) == 1:
            signed_count += 1

    return {
        "count": signed_count,
        "signedCount": signed_count,
        "sign_tchplan_num": signed_count,
        "signed_tchplan_num": signed_count,
    }


def _build_board_main_data_content(store: MirrorStore, request: Request) -> dict[str, Any]:
    metrics = _build_dashboard_metric_snapshot(store, request, b"")

    return {
        "intendNum": metrics["intendNum"],
        "todayIntendNum": metrics["todayIntendNum"],
        "todayComeNum": metrics["todayComeNum"],
        "formalNum": metrics["formalNum"],
        "tryNum": metrics["tryNum"],
        "todayFormalNum": metrics["todayFormalNum"],
        "todayTryNum": metrics["todayTryNum"],
        "lessonRecordNum": metrics["lessonRecordNum"],
        "todayLessonRecordNum": metrics["todayLessonRecordNum"],
        "inCome": metrics["inCome"],
        "consumeHour": metrics["consumeHour"],
        "todayInCome": metrics["todayInCome"],
        "todayConsumeHour": metrics["todayConsumeHour"],
        "income": 0,
        "totalIncome": 0,
        "totalLessonHour": metrics["consumeHour"],
        "todayIncome": 0,
        "todayLessonHour": metrics["todayConsumeHour"],
    }


def _parse_dashboard_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    if not text:
        return None

    normalized = text.replace("T", " ").replace("/", "-")
    if normalized.endswith("Z"):
        normalized = normalized[:-1]
    for candidate in (normalized, normalized[:19], normalized.split(".", 1)[0]):
        candidate = candidate.strip()
        if not candidate:
            continue
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(candidate, fmt)
            except ValueError:
                continue

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None)
    return parsed


def _dashboard_requested_date_window(start_value: Any, end_value: Any) -> tuple[datetime | None, datetime | None]:
    start_dt = _parse_dashboard_datetime(start_value)
    end_dt = _parse_dashboard_datetime(end_value)
    if start_dt is not None and end_dt is not None and end_dt < start_dt:
        start_dt, end_dt = end_dt, start_dt
    return start_dt, end_dt


def _dashboard_series_bounds(
    start_dt: datetime | None,
    end_dt: datetime | None,
    fallback_moments: list[datetime] | None = None,
) -> tuple[datetime, datetime]:
    fallback_values = [moment for moment in (fallback_moments or []) if isinstance(moment, datetime)]
    if start_dt is None and end_dt is None:
        if fallback_values:
            start_dt = min(fallback_values)
            end_dt = max(fallback_values)
        else:
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=6)
    elif start_dt is None and end_dt is not None:
        start_dt = end_dt - timedelta(days=6)
    elif start_dt is not None and end_dt is None:
        end_dt = start_dt + timedelta(days=6)

    assert start_dt is not None
    assert end_dt is not None

    start_dt = datetime(start_dt.year, start_dt.month, start_dt.day)
    end_dt = datetime(end_dt.year, end_dt.month, end_dt.day)
    if end_dt < start_dt:
        start_dt, end_dt = end_dt, start_dt
    if (end_dt - start_dt).days > 120:
        start_dt = end_dt - timedelta(days=120)
    return start_dt, end_dt


def _dashboard_series_date_list(start_dt: datetime, end_dt: datetime) -> list[str]:
    values: list[str] = []
    current = start_dt
    while current <= end_dt:
        values.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return values


def _dashboard_in_requested_window(moment: datetime | None, start_dt: datetime | None, end_dt: datetime | None) -> bool:
    if moment is None:
        return start_dt is None and end_dt is None
    current_day = moment.date()
    if start_dt is not None and current_day < start_dt.date():
        return False
    if end_dt is not None and current_day > end_dt.date():
        return False
    return True


def _dashboard_reference_day(end_dt: datetime | None) -> str:
    if end_dt is not None:
        return end_dt.strftime("%Y-%m-%d")
    return datetime.now().strftime("%Y-%m-%d")


def _dashboard_campus_name_id_map(store: MirrorStore) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for campus in store.list_user_campuses():
        if not isinstance(campus, dict):
            continue
        campus_id = _coerce_int(
            campus.get("dept_id")
            or campus.get("id")
            or campus.get("eduCampusId")
            or campus.get("campusId")
        )
        if campus_id is None:
            continue
        for key in ("campusName", "dept_name", "name"):
            campus_name = str(campus.get(key) or "").strip()
            if campus_name:
                mapping[campus_name] = campus_id
    primary_name = _teacher_primary_campus_name(store)
    primary_id = _teacher_primary_campus_id(store)
    if primary_name and primary_id is not None:
        mapping.setdefault(primary_name, primary_id)
    return mapping


def _canonical_campus_id_alias_map(store: MirrorStore) -> dict[int, int]:
    alias_map: dict[int, int] = {}
    for campus in store.list_user_campuses():
        if not isinstance(campus, dict):
            continue
        canonical_id = _coerce_int(
            campus.get("dept_id")
            or campus.get("eduCampusId")
            or campus.get("campusId")
            or campus.get("educationalInstitutionCampusId")
            or campus.get("educational_institution_campus_id")
            or campus.get("id")
        )
        if canonical_id is None:
            continue
        for key in (
            "id",
            "dept_id",
            "eduCampusId",
            "campusId",
            "educationalInstitutionCampusId",
            "educational_institution_campus_id",
        ):
            alias_id = _coerce_int(campus.get(key))
            if alias_id is not None:
                alias_map[alias_id] = canonical_id
    return alias_map


def _normalize_store_campus_ids(store: MirrorStore, campus_ids: list[int]) -> list[int]:
    alias_map = _canonical_campus_id_alias_map(store)
    normalized_ids: list[int] = []
    for campus_id in campus_ids:
        _append_unique_int(normalized_ids, alias_map.get(campus_id, campus_id))
    return normalized_ids


def _dashboard_requested_campus_ids(
    store: MirrorStore,
    request: Request,
    payload: Any,
    *keys: str,
) -> list[int]:
    campus_ids: list[int] = []
    body = payload if isinstance(payload, dict) else {}
    for key in keys:
        if key in body:
            for campus_id in _extract_campus_ids(body.get(key)):
                _append_unique_int(campus_ids, campus_id)
        query_value = _first_query_value(request, key)
        if query_value not in (None, ""):
            for campus_id in _extract_campus_ids(query_value):
                _append_unique_int(campus_ids, campus_id)
    if campus_ids:
        return _normalize_store_campus_ids(store, campus_ids)
    for campus_id in _teacher_selected_school_ids(store):
        _append_unique_int(campus_ids, campus_id)
    primary_campus_id = _teacher_primary_campus_id(store)
    if primary_campus_id is not None:
        _append_unique_int(campus_ids, primary_campus_id)
    return _normalize_store_campus_ids(store, campus_ids)


def _dashboard_student_snapshots(store: MirrorStore) -> list[dict[str, Any]]:
    campus_name_map = _dashboard_campus_name_id_map(store)
    fallback_campus_id = _teacher_primary_campus_id(store) or 0
    rows: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for row in _build_select_study_rows(store):
        if not isinstance(row, dict):
            continue
        student_id = _coerce_int(row.get("stuId") or row.get("id"))
        if student_id is None or student_id in seen_ids:
            continue
        seen_ids.add(student_id)
        campus_id = _coerce_int(
            row.get("eduCampusId")
            or row.get("campusId")
            or row.get("educational_institution_campus_id")
        )
        if campus_id is None:
            campus_name = str(row.get("eduCampusName") or row.get("campusName") or row.get("schoolName") or "").strip()
            campus_id = campus_name_map.get(campus_name) or fallback_campus_id
        student_type = str(row.get("studentType") or row.get("stuType") or "").strip().lower()
        is_trial = student_type in {"trial", "try", "试听", "璇曞惉"} or str(row.get("isTry") or "").strip() in {"1", "true", "True"}
        rows.append(
            {
                "id": student_id,
                "campus_id": campus_id or fallback_campus_id,
                "created_time": str(row.get("createdTime") or row.get("created_time") or "").strip(),
                "is_trial": is_trial,
            }
        )
    return rows


def _dashboard_class_size_map(store: MirrorStore) -> dict[int, int]:
    fallback_total = max(len(_dashboard_student_snapshots(store)), 1)
    size_by_class: dict[int, int] = {}
    for class_row in store.list_classes():
        if not isinstance(class_row, dict):
            continue
        class_id = _coerce_int(class_row.get("id"))
        if class_id is None:
            continue
        payload = store.get_class_student_payload(class_id) or {}
        total = _parse_int_like(
            payload.get("total")
            or payload.get("totalSize")
            or payload.get("pageTotal")
            or payload.get("count")
        )
        if total is None:
            student_rows = payload.get("studentList") or payload.get("content") or payload.get("rows") or []
            if isinstance(student_rows, list):
                total = len(student_rows)
        size_by_class[class_id] = total if total not in (None, 0) else fallback_total
    return size_by_class


def _dashboard_plan_snapshots(store: MirrorStore) -> list[dict[str, Any]]:
    subject_name_map = _teacher_subject_name_map(store)
    class_size_map = _dashboard_class_size_map(store)
    fallback_campus_id = _teacher_primary_campus_id(store) or 0
    fallback_due_num = max(len(_dashboard_student_snapshots(store)), 1)
    rows: list[dict[str, Any]] = []
    for plan in store.list_teaching_plans():
        if not isinstance(plan, dict):
            continue
        class_info = plan.get("classInfo") if isinstance(plan.get("classInfo"), dict) else {}
        class_id = _coerce_int(class_info.get("id") or plan.get("curriculum_class_id"))
        campus_id = _coerce_int(
            plan.get("educational_institution_campus_id")
            or class_info.get("educational_institution_campus_id")
            or fallback_campus_id
        ) or fallback_campus_id
        subject_id = _coerce_int(plan.get("subject_id"))
        if subject_id is None:
            subject_info_list = class_info.get("subjectInfoList") if isinstance(class_info.get("subjectInfoList"), list) else []
            if subject_info_list:
                subject_id = _coerce_int((subject_info_list[0] or {}).get("id"))
        subject_name = subject_name_map.get(subject_id or -1) or ""
        if not subject_name:
            subject_info_list = class_info.get("subjectInfoList") if isinstance(class_info.get("subjectInfoList"), list) else []
            if subject_info_list and isinstance(subject_info_list[0], dict):
                subject_name = str(subject_info_list[0].get("name") or "").strip()
        lecturer_name = str(
            plan.get("lecturerName")
            or class_info.get("lecturerName")
            or class_info.get("lectureName")
            or ""
        ).strip()
        lesson_title = str(
            plan.get("custom_lesson_title")
            or ((plan.get("lessionInfo") or {}).get("title") if isinstance(plan.get("lessionInfo"), dict) else None)
            or plan.get("title")
            or ""
        ).strip()
        class_datetime = _parse_dashboard_datetime(plan.get("start_class_date") or plan.get("class_date"))
        due_num = class_size_map.get(class_id or -1, fallback_due_num)
        start_text = str(plan.get("start_class_date") or plan.get("class_date") or "").strip()
        end_text = str(plan.get("end_class_date") or "").strip()
        class_time = start_text
        if start_text and end_text:
            class_time = f"{start_text} - {end_text}"
        rows.append(
            {
                "id": _coerce_int(plan.get("id")) or 0,
                "tchPlanId": _coerce_int(plan.get("id")) or 0,
                "teachingPlanId": _coerce_int(plan.get("id")) or 0,
                "lecturer_id": _coerce_int(plan.get("lecturer_id") or class_info.get("lecturer_id")) or 0,
                "lessonId": _coerce_int(plan.get("curriculum_meterial_id"))
                or _coerce_int(((plan.get("lessionInfo") or {}).get("id") if isinstance(plan.get("lessionInfo"), dict) else None))
                or 0,
                "campus_id": campus_id,
                "class_id": class_id or 0,
                "className": str(class_info.get("name") or plan.get("className") or "").strip(),
                "tchName": lecturer_name,
                "title": lesson_title,
                "subjectCode": str(subject_id or 0),
                "subjectName": subject_name,
                "class_datetime": class_datetime,
                "classTime": class_time,
                "sign_state": _coerce_int(plan.get("sign_state") or plan.get("sign_state_new")) or 0,
                "cost_lesson_hour": _teaching_plan_cost_lesson_hour(plan),
                "dueNum": due_num,
                "realNum": due_num if _coerce_int(plan.get("sign_state") or plan.get("sign_state_new")) == 1 else 0,
                "lessonWork": f"0 / {due_num}",
                "homeWork": f"0 / {due_num}",
                "commentRealNum": 0,
                "commentDueNum": due_num,
            }
        )
    return rows


def _build_dashboard_metric_snapshot(
    store: MirrorStore,
    request: Request,
    request_body: bytes,
) -> dict[str, Any]:
    submitted = _load_request_payload(request_body)
    campus_ids = _dashboard_requested_campus_ids(
        store,
        request,
        submitted,
        "eduCampusId",
        "eduCampusIdList",
        "campusIds",
        "campusIdArr",
    )
    campus_filter = set(campus_ids)
    students = [
        row
        for row in _dashboard_student_snapshots(store)
        if not campus_filter or _coerce_int(row.get("campus_id")) in campus_filter
    ]
    plans = [
        row
        for row in _dashboard_plan_snapshots(store)
        if not campus_filter or _coerce_int(row.get("campus_id")) in campus_filter
    ]

    start_dt, end_dt = _dashboard_requested_date_window(
        _request_payload_value(request, submitted, "startDate", "start_date"),
        _request_payload_value(request, submitted, "endDate", "end_date"),
    )
    reference_day = _dashboard_reference_day(end_dt)
    ranged_plans = [
        row
        for row in plans
        if _dashboard_in_requested_window(row.get("class_datetime"), start_dt, end_dt)
    ]

    formal_num = sum(1 for student in students if not student.get("is_trial"))
    try_num = sum(1 for student in students if student.get("is_trial"))
    today_formal_num = sum(
        1
        for student in students
        if not student.get("is_trial") and str(student.get("created_time") or "").startswith(reference_day)
    )
    today_try_num = sum(
        1
        for student in students
        if student.get("is_trial") and str(student.get("created_time") or "").startswith(reference_day)
    )
    consume_hour = round(sum(_coerce_float_like(plan.get("cost_lesson_hour"), 0.0) for plan in ranged_plans), 2)
    today_lesson_plans = [
        plan
        for plan in ranged_plans
        if str(plan.get("classTime") or "").startswith(reference_day)
        or str((plan.get("class_datetime") or "").date() if plan.get("class_datetime") else "").startswith(reference_day)
    ]
    today_consume_hour = round(sum(_coerce_float_like(plan.get("cost_lesson_hour"), 0.0) for plan in today_lesson_plans), 2)

    return {
        "intendNum": 0,
        "todayIntendNum": 0,
        "todayComeNum": 0,
        "formalNum": formal_num,
        "tryNum": try_num,
        "todayFormalNum": today_formal_num,
        "todayTryNum": today_try_num,
        "lessonRecordNum": len(ranged_plans),
        "todayLessonRecordNum": len(today_lesson_plans),
        "inCome": 0,
        "consumeHour": consume_hour,
        "todayInCome": 0,
        "todayConsumeHour": today_consume_hour,
    }


def _build_dashboard_clue_chart_content(store: MirrorStore, request: Request, request_body: bytes) -> dict[str, Any]:
    submitted = _load_request_payload(request_body)
    start_dt, end_dt = _dashboard_requested_date_window(
        _request_payload_value(request, submitted, "startDate", "start_date"),
        _request_payload_value(request, submitted, "endDate", "end_date"),
    )
    bounds_start, bounds_end = _dashboard_series_bounds(start_dt, end_dt)
    date_list = _dashboard_series_date_list(bounds_start, bounds_end)
    zero_list = [0 for _ in date_list]
    return {
        "dateList": date_list,
        "intendNumList": _json_deep_copy(zero_list),
        "comeNumList": _json_deep_copy(zero_list),
    }


def _build_dashboard_student_pie_content(store: MirrorStore, request: Request, request_body: bytes) -> dict[str, Any]:
    metrics = _build_dashboard_metric_snapshot(store, request, request_body)
    return {
        "formalNum": metrics["formalNum"],
        "tryNum": metrics["tryNum"],
    }


def _build_dashboard_teacher_record_chart_content(store: MirrorStore, request: Request, request_body: bytes) -> dict[str, Any]:
    submitted = _load_request_payload(request_body)
    campus_ids = _dashboard_requested_campus_ids(store, request, submitted, "eduCampusId")
    campus_filter = set(campus_ids)
    start_dt, end_dt = _dashboard_requested_date_window(
        _request_payload_value(request, submitted, "startDate", "start_date"),
        _request_payload_value(request, submitted, "endDate", "end_date"),
    )
    by_teacher: dict[str, dict[str, Any]] = {}
    for plan in _dashboard_plan_snapshots(store):
        if campus_filter and _coerce_int(plan.get("campus_id")) not in campus_filter:
            continue
        if not _dashboard_in_requested_window(plan.get("class_datetime"), start_dt, end_dt):
            continue
        teacher_name = str(plan.get("tchName") or "Unknown Teacher").strip() or "Unknown Teacher"
        entry = by_teacher.setdefault(
            teacher_name,
            {"hour": 0.0, "num": 0},
        )
        entry["hour"] += _coerce_float_like(plan.get("cost_lesson_hour"), 0.0)
        entry["num"] += 1

    ordered_rows = sorted(by_teacher.items(), key=lambda item: (-item[1]["hour"], item[0]))
    return {
        "hourNameList": [name for name, _ in ordered_rows],
        "hourList": [round(stats["hour"], 2) for _, stats in ordered_rows],
        "numNameList": [name for name, _ in ordered_rows],
        "numList": [stats["num"] for _, stats in ordered_rows],
    }


def _build_dashboard_student_consume_chart_content(store: MirrorStore, request: Request, request_body: bytes) -> dict[str, Any]:
    submitted = _load_request_payload(request_body)
    campus_ids = _dashboard_requested_campus_ids(
        store,
        request,
        submitted,
        "eduCampusIdList",
        "campusIds",
        "campusIdArr",
        "eduCampusId",
    )
    campus_filter = set(campus_ids)
    matching_plans = [
        plan
        for plan in _dashboard_plan_snapshots(store)
        if not campus_filter or _coerce_int(plan.get("campus_id")) in campus_filter
    ]
    start_dt, end_dt = _dashboard_requested_date_window(
        _request_payload_value(request, submitted, "startDate", "start_date"),
        _request_payload_value(request, submitted, "endDate", "end_date"),
    )
    fallback_dates = [plan["class_datetime"] for plan in matching_plans if isinstance(plan.get("class_datetime"), datetime)]
    bounds_start, bounds_end = _dashboard_series_bounds(start_dt, end_dt, fallback_dates)
    date_list = _dashboard_series_date_list(bounds_start, bounds_end)
    date_index = {day: index for index, day in enumerate(date_list)}

    consume_rows: list[dict[str, Any]] = []
    for campus_id in campus_ids:
        consume_rows.append(
            {
                "id": campus_id,
                "lessonHourList": [0.0 for _ in date_list],
                "lessonNumList": [0 for _ in date_list],
                "itemStyle": {},
            }
        )
    consume_by_campus = {row["id"]: row for row in consume_rows}
    for plan in matching_plans:
        plan_dt = plan.get("class_datetime")
        if not isinstance(plan_dt, datetime):
            continue
        if not _dashboard_in_requested_window(plan_dt, start_dt, end_dt):
            continue
        campus_id = _coerce_int(plan.get("campus_id"))
        if campus_id is None or campus_id not in consume_by_campus:
            continue
        date_key = plan_dt.strftime("%Y-%m-%d")
        if date_key not in date_index:
            continue
        slot = date_index[date_key]
        consume_by_campus[campus_id]["lessonHourList"][slot] += round(_coerce_float_like(plan.get("cost_lesson_hour"), 0.0), 2)
        consume_by_campus[campus_id]["lessonNumList"][slot] += 1

    return {
        "dateList": date_list,
        "consumeVoList": consume_rows,
    }


def _build_dashboard_teacher_attendance_content(store: MirrorStore, request: Request, request_body: bytes) -> dict[str, Any]:
    submitted = _load_request_payload(request_body)
    campus_ids = _dashboard_requested_campus_ids(store, request, submitted, "eduCampusId")
    campus_filter = set(campus_ids)
    start_dt, end_dt = _dashboard_requested_date_window(
        _request_payload_value(request, submitted, "startDate", "start_date"),
        _request_payload_value(request, submitted, "endDate", "end_date"),
    )
    attendance_by_teacher: dict[str, dict[str, int]] = {}
    for plan in _dashboard_plan_snapshots(store):
        if campus_filter and _coerce_int(plan.get("campus_id")) not in campus_filter:
            continue
        if not _dashboard_in_requested_window(plan.get("class_datetime"), start_dt, end_dt):
            continue
        teacher_name = str(plan.get("tchName") or "Unknown Teacher").strip() or "Unknown Teacher"
        entry = attendance_by_teacher.setdefault(teacher_name, {"total": 0, "signed": 0})
        entry["total"] += 1
        if _coerce_int(plan.get("sign_state")) == 1:
            entry["signed"] += 1

    ordered_rows = sorted(attendance_by_teacher.items(), key=lambda item: (-item[1]["total"], item[0]))
    return {
        "tchNameList": [name for name, _ in ordered_rows],
        "rateList": [
            round((stats["signed"] / stats["total"]) * 100, 2) if stats["total"] else 0
            for _, stats in ordered_rows
        ],
    }


def _build_dashboard_campus_attendance_content(store: MirrorStore, request: Request, request_body: bytes) -> dict[str, Any]:
    submitted = _load_request_payload(request_body)
    campus_ids = _dashboard_requested_campus_ids(store, request, submitted, "eduCampusIdList", "campusIds", "campusIdArr")
    campus_filter = set(campus_ids)
    start_dt, end_dt = _dashboard_requested_date_window(
        _request_payload_value(request, submitted, "startDate", "start_date"),
        _request_payload_value(request, submitted, "endDate", "end_date"),
    )
    totals_by_campus: dict[int, dict[str, int]] = {campus_id: {"total": 0, "signed": 0} for campus_id in campus_ids}
    for plan in _dashboard_plan_snapshots(store):
        campus_id = _coerce_int(plan.get("campus_id"))
        if campus_id is None or (campus_filter and campus_id not in campus_filter):
            continue
        if not _dashboard_in_requested_window(plan.get("class_datetime"), start_dt, end_dt):
            continue
        entry = totals_by_campus.setdefault(campus_id, {"total": 0, "signed": 0})
        entry["total"] += 1
        if _coerce_int(plan.get("sign_state")) == 1:
            entry["signed"] += 1

    ordered_ids = [campus_id for campus_id in campus_ids if campus_id in totals_by_campus]
    return {
        "eduCampusIdList": ordered_ids,
        "percentList": [
            round((totals_by_campus[campus_id]["signed"] / totals_by_campus[campus_id]["total"]) * 100, 2)
            if totals_by_campus[campus_id]["total"]
            else 0
            for campus_id in ordered_ids
        ],
    }


def _build_dashboard_campus_consume_content(store: MirrorStore, request: Request, request_body: bytes) -> dict[str, Any]:
    submitted = _load_request_payload(request_body)
    campus_ids = _dashboard_requested_campus_ids(store, request, submitted, "eduCampusIdList", "campusIds", "campusIdArr")
    campus_filter = set(campus_ids)
    start_dt, end_dt = _dashboard_requested_date_window(
        _request_payload_value(request, submitted, "startDate", "start_date"),
        _request_payload_value(request, submitted, "endDate", "end_date"),
    )
    hours_by_campus: dict[int, float] = {campus_id: 0.0 for campus_id in campus_ids}
    for plan in _dashboard_plan_snapshots(store):
        campus_id = _coerce_int(plan.get("campus_id"))
        if campus_id is None or (campus_filter and campus_id not in campus_filter):
            continue
        if not _dashboard_in_requested_window(plan.get("class_datetime"), start_dt, end_dt):
            continue
        hours_by_campus[campus_id] = round(
            hours_by_campus.get(campus_id, 0.0) + _coerce_float_like(plan.get("cost_lesson_hour"), 0.0),
            2,
        )

    ordered_ids = [campus_id for campus_id in campus_ids if campus_id in hours_by_campus]
    return {
        "eduCampusIdList": ordered_ids,
        "numList": [hours_by_campus[campus_id] for campus_id in ordered_ids],
    }


def _build_dashboard_teacher_rows(store: MirrorStore, request: Request, request_body: bytes) -> list[dict[str, Any]]:
    submitted = _load_request_payload(request_body)
    campus_ids = _dashboard_requested_campus_ids(
        store,
        request,
        submitted,
        "eduCampusIdList",
        "campusIds",
        "campusIdArr",
        "eduCampusId",
    )
    campus_filter = set(campus_ids)
    rows_by_id: dict[int, dict[str, Any]] = {}
    for plan in _dashboard_plan_snapshots(store):
        campus_id = _coerce_int(plan.get("campus_id"))
        if campus_filter and campus_id not in campus_filter:
            continue
        teacher_name = str(plan.get("tchName") or "").strip()
        teacher_id = _coerce_int(plan.get("lecturer_id")) or _coerce_int(plan.get("id")) or 0
        if not teacher_name or teacher_id in rows_by_id:
            continue
        rows_by_id[teacher_id] = {
            "id": teacher_id,
            "userId": teacher_id,
            "realName": teacher_name,
            "name": teacher_name,
            "campusId": campus_id or 0,
        }
    return sorted(rows_by_id.values(), key=lambda row: (str(row.get("realName") or ""), _coerce_int(row.get("id")) or 0))


def _build_dashboard_class_comment_content(store: MirrorStore, request: Request, request_body: bytes) -> dict[str, Any]:
    submitted = _load_request_payload(request_body)
    campus_ids = _dashboard_requested_campus_ids(store, request, submitted, "eduCampusId")
    campus_filter = set(campus_ids)
    start_dt, end_dt = _dashboard_requested_date_window(
        _request_payload_value(request, submitted, "startDate", "start_date"),
        _request_payload_value(request, submitted, "endDate", "end_date"),
    )
    teacher_name_filter = str(
        _request_payload_value(request, submitted, "tchName", "lecturerName", "realName") or ""
    ).strip()

    rows: list[dict[str, Any]] = []
    for plan in _dashboard_plan_snapshots(store):
        campus_id = _coerce_int(plan.get("campus_id"))
        if campus_filter and campus_id not in campus_filter:
            continue
        if not _dashboard_in_requested_window(plan.get("class_datetime"), start_dt, end_dt):
            continue
        if teacher_name_filter and str(plan.get("tchName") or "").strip() != teacher_name_filter:
            continue
        rows.append(
            {
                "id": plan.get("id") or 0,
                "tchPlanId": plan.get("tchPlanId") or 0,
                "teachingPlanId": plan.get("tchPlanId") or 0,
                "lessonId": plan.get("lessonId") or 0,
                "subjectCode": plan.get("subjectCode") or "0",
                "subjectName": plan.get("subjectName") or "",
                "className": plan.get("className") or "",
                "tchName": plan.get("tchName") or "",
                "title": plan.get("title") or "",
                "classTime": plan.get("classTime") or "",
                "realNum": plan.get("realNum") or 0,
                "dueNum": plan.get("dueNum") or 0,
                "lessonWork": plan.get("lessonWork") or "0 / 0",
                "homeWork": plan.get("homeWork") or "0 / 0",
                "commentRealNum": plan.get("commentRealNum") or 0,
                "commentDueNum": plan.get("commentDueNum") or 0,
            }
        )

    rows.sort(
        key=lambda row: (
            str(row.get("classTime") or ""),
            _coerce_int(row.get("tchPlanId")) or 0,
        ),
        reverse=True,
    )
    page_num, page_size = _page_request_window(submitted)
    start = (page_num - 1) * page_size
    page_rows = rows[start:start + page_size]
    return {
        "pageNum": page_num,
        "pageSize": page_size,
        "totalSize": len(rows),
        "totalPages": 0 if not rows else (len(rows) + page_size - 1) // page_size,
        "content": page_rows,
        "records": page_rows,
        "rows": page_rows,
        "list": page_rows,
    }


def _build_exam_student_statistics_content(store: MirrorStore, request_body: bytes) -> dict[str, Any]:
    submitted = _load_request_payload(request_body)
    page_num, page_size = _page_request_window(submitted)
    keyword = ""
    if isinstance(submitted, dict):
        keyword = str(submitted.get("keyword") or "").strip().lower()

    rows: list[dict[str, Any]] = []
    for index, student in enumerate(store.list_local_students(), start=1):
        student_name = _student_display_name(student, default_id=student.get("id") or index).strip()
        student_account = str(student.get("name") or student.get("username") or "").strip()
        if keyword and keyword not in student_name.lower() and keyword not in student_account.lower():
            continue
        student_id = _coerce_int(student.get("id")) or index
        rows.append(
            {
                "id": student_id,
                "studentId": student_id,
                "studentName": student_name or student_account or f"Student {student_id}",
                "studentAccount": student_account or f"student-{student_id}",
                "examCount": 0,
                "practiceCount": 0,
                "lessonExamCount": 0,
                "wrongQuestionCount": 0,
                "avatar": student.get("headimg_url") or "",
            }
        )

    start = (page_num - 1) * page_size
    page_rows = rows[start:start + page_size]
    total_size = len(rows)
    return {
        "pageNum": page_num,
        "pageSize": page_size,
        "totalSize": total_size,
        "totalPages": 0 if total_size == 0 else (total_size + page_size - 1) // page_size,
        "content": page_rows,
        "records": page_rows,
        "rows": page_rows,
        "list": page_rows,
    }


def _request_payload_value(request: Request, payload: Any, *keys: str) -> Any:
    body = payload if isinstance(payload, dict) else {}
    for key in keys:
        value = body.get(key)
        if value not in (None, ""):
            return value
    for key in keys:
        value = _first_query_value(request, key)
        if value not in (None, ""):
            return value
    return None


def _competition_student_snapshots(store: MirrorStore, *, keyword: str | None = None) -> list[dict[str, Any]]:
    normalized_keyword = (keyword or "").strip().lower()
    rows: list[dict[str, Any]] = []
    for index, student in enumerate(store.list_local_students(), start=1):
        student_id = _coerce_int(student.get("id")) or index
        student_name = _student_display_name(student, default_id=student_id).strip()
        student_account = str(student.get("name") or student.get("username") or "").strip()
        if not student_name:
            student_name = student_account or f"Student {student_id}"
        if not student_account:
            student_account = f"student-{student_id}"
        if normalized_keyword and normalized_keyword not in student_name.lower() and normalized_keyword not in student_account.lower():
            continue
        rows.append(
            {
                "studentId": student_id,
                "studentName": student_name,
                "studentAccount": student_account,
                "avatar": student.get("headimg_url") or student.get("headimgUrl") or "",
                "campusId": (
                    _coerce_int(student.get("educational_institution_campus_id") or student.get("eduCampusId"))
                    or _teacher_primary_campus_id(store)
                    or 0
                ),
            }
        )
    return rows


def _competition_question_subject_id(store: MirrorStore) -> int:
    subject_rows = _teacher_subject_catalog(store)
    if subject_rows:
        subject_id = _coerce_int(subject_rows[0].get("id"))
        if subject_id is not None:
            return subject_id
    return 1


def _competition_question_rows(store: MirrorStore, context_id: int, *, title_prefix: str) -> list[dict[str, Any]]:
    subject_id = _competition_question_subject_id(store)
    question_id = max(context_id, 1) * 100 + 1
    return [
        {
            "questionNo": 1,
            "questionId": question_id,
            "type": 1,
            "subjectId": subject_id,
            "subject_id": subject_id,
            "title": f"{title_prefix}鍗曢€夐 1",
            "isAnswered": True,
            "isCorrect": 1,
        }
    ]


def _competition_question_analysis_content(
    store: MirrorStore,
    context_id: int,
    question_id: int,
    *,
    title_prefix: str,
) -> dict[str, Any]:
    del store
    options_rows = [
        {"title": "A", "content": "鏈湴闀滃儚绛旀 A"},
        {"title": "B", "content": "鏈湴闀滃儚绛旀 B"},
        {"title": "C", "content": "鏈湴闀滃儚绛旀 C"},
        {"title": "D", "content": "鏈湴闀滃儚绛旀 D"},
    ]
    options_text = json.dumps(options_rows, ensure_ascii=False)
    return {
        "id": question_id,
        "questionId": question_id,
        "examId": context_id,
        "questionNo": 1,
        "type": 1,
        "subjectId": 1,
        "subject_id": 1,
        "title": f"{title_prefix}鍗曢€夐 1",
        "titleOther": "",
        "title_other": "",
        "showType": 1,
        "show_type": 1,
        "options": options_text,
        "options_md": options_text,
        "answer": "A",
        "studentAnswer": "A",
        "stu_answer": "A",
        "analysis": "This explanation is generated by the local mirror fallback so the question detail page can render fully offline.",
        "analysis_md": "",
        "stuExamQuestionInfo": {"answer_state": "1"},
        "scoreDistribution": {
            "fullScoreNum": 1,
            "fullScoreRate": 100,
            "partialScoreNum": 0,
            "partialScoreRate": 0,
            "zeroScoreNum": 0,
            "zeroScoreRate": 0,
        },
        "rightRate": 100,
        "submitTimes": 1,
        "stuCode": "",
        "isMarkdown": False,
    }


def _build_competition_practice_records_content(store: MirrorStore, request_body: bytes) -> dict[str, Any]:
    submitted = _load_request_payload(request_body)
    page_num, page_size = _page_request_window(submitted, default_page_size=10)
    keyword = str((submitted or {}).get("examName") or "").strip().lower()
    rows: list[dict[str, Any]] = []
    today = datetime.now().strftime("%Y-%m-%d")
    for student in _competition_student_snapshots(store, keyword=keyword):
        exam_id = 810000 + student["studentId"]
        rows.append(
            {
                "id": exam_id,
                "examId": exam_id,
                "examName": f"鏈湴闀滃儚缁冧範 {student['studentName']}",
                "startDate": today,
                "endDate": today,
                "totalQuestions": 1,
                "submitStatus": 1,
                "isSubmitted": True,
            }
        )
    start = (page_num - 1) * page_size
    page_rows = rows[start:start + page_size]
    total_size = len(rows)
    return {
        "pageNum": page_num,
        "pageSize": page_size,
        "totalSize": total_size,
        "totalPages": 0 if total_size == 0 else (total_size + page_size - 1) // page_size,
        "content": page_rows,
        "records": page_rows,
        "rows": page_rows,
        "list": page_rows,
    }


def _build_competition_exam_records_content(store: MirrorStore, request_body: bytes) -> dict[str, Any]:
    submitted = _load_request_payload(request_body)
    page_num, page_size = _page_request_window(submitted, default_page_size=10)
    keyword = str((submitted or {}).get("examName") or "").strip().lower()
    record_type = _parse_int_like((submitted or {}).get("type")) or 3
    total_students = max(len(store.list_local_students()), 1)
    title_prefix = "鏈湴闅忓爞娴嬭瘯" if record_type == 2 else "鏈湴闃舵鑰冭瘯"
    rows: list[dict[str, Any]] = []
    today = datetime.now().strftime("%Y-%m-%d")
    for student in _competition_student_snapshots(store, keyword=keyword):
        exam_id = 820000 + student["studentId"] * 10 + record_type
        rows.append(
            {
                "id": exam_id,
                "examId": exam_id,
                "examName": f"{title_prefix} {student['studentName']}",
                "startDate": today,
                "endDate": today,
                "duration": 10,
                "totalQuestions": 1,
                "submitStatus": 1,
                "isSubmitted": True,
                "score": 100,
                "rank": 1,
                "totalStudents": total_students,
                "usedTime": 8,
            }
        )
    start = (page_num - 1) * page_size
    page_rows = rows[start:start + page_size]
    total_size = len(rows)
    return {
        "pageNum": page_num,
        "pageSize": page_size,
        "totalSize": total_size,
        "totalPages": 0 if total_size == 0 else (total_size + page_size - 1) // page_size,
        "content": page_rows,
        "records": page_rows,
        "rows": page_rows,
        "list": page_rows,
    }


def _build_competition_exam_detail_content(
    store: MirrorStore,
    request: Request,
    request_body: bytes,
    *,
    practice: bool,
) -> dict[str, Any]:
    submitted = _load_request_payload(request_body)
    exam_id = _parse_int_like(_request_payload_value(request, submitted, "examId", "id", "testExamId")) or 1
    title_prefix = "鏈湴闀滃儚缁冧範" if practice else "鏈湴闀滃儚鑰冭瘯"
    title = f"{title_prefix} {exam_id}"
    content = {
        "id": exam_id,
        "examId": exam_id,
        "title": title,
        "examName": title,
        "questionNum": 1,
        "questionCount": 1,
        "totalQuestions": 1,
        "duration": 10,
        "passScore": 60,
        "passscore": 60,
    }
    if practice:
        started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        content["dataList"] = [
            {
                "id": exam_id * 10 + 1,
                "test_exam_id": exam_id,
                "examId": exam_id,
                "isRecord": 1,
                "right_num": 1,
                "wrong_num": 0,
                "start_time": started_at,
                "created_time": started_at,
            }
        ]
    return content


def _build_competition_question_guide_content(
    store: MirrorStore,
    request: Request,
    request_body: bytes,
    *,
    practice: bool,
) -> dict[str, Any]:
    submitted = _load_request_payload(request_body)
    context_id = _parse_int_like(_request_payload_value(request, submitted, "examId", "id", "testExamId")) or 1
    title_prefix = "鏈湴缁冧範" if practice else "鏈湴鑰冭瘯"
    question_list = _competition_question_rows(store, context_id, title_prefix=title_prefix)
    statistics = {
        "correctCount": 1,
        "wrongCount": 0,
        "partiallyCorrectCount": 0,
        "unansweredCount": 0,
    }
    return {
        "questionList": question_list,
        "list": question_list,
        "statistics": statistics,
    }


def _build_competition_question_analysis_response(
    store: MirrorStore,
    request: Request,
    request_body: bytes,
    *,
    practice: bool,
) -> dict[str, Any]:
    submitted = _load_request_payload(request_body)
    context_id = _parse_int_like(_request_payload_value(request, submitted, "examId", "id", "testExamId")) or 1
    question_id = _parse_int_like(_request_payload_value(request, submitted, "questionId")) or context_id * 100 + 1
    title_prefix = "鏈湴缁冧範" if practice else "鏈湴鑰冭瘯"
    return _competition_question_analysis_content(store, context_id, question_id, title_prefix=title_prefix)


def _build_competition_wrong_question_statistics_content(
    store: MirrorStore,
    request_body: bytes,
) -> dict[str, Any]:
    del request_body
    total = max(len(store.list_local_students()), 1)
    question_type_rows = [
        {
            "questionType": "1",
            "questionTypeName": "鍗曢€夐",
            "wrongCount": total,
            "rate": 100,
        }
    ]
    knowledge_rows = [
        {
            "knowledgePointName": "Local Mirror Knowledge Point",
            "wrongCount": total,
            "rate": 100,
        }
    ]
    return {
        "wrongQuestionCount": total,
        "questionTypeStatistics": question_type_rows,
        "questionTypeRateList": question_type_rows,
        "knowledgePointStatistics": knowledge_rows,
        "knowledgePointRateList": knowledge_rows,
        "totalContent": {
            "wrongQuestionCount": total,
            "questionCount": total,
        },
    }


def _build_competition_wrong_question_list_content(store: MirrorStore, request_body: bytes) -> dict[str, Any]:
    submitted = _load_request_payload(request_body)
    page_num, page_size = _page_request_window(submitted, default_page_size=10)
    keyword = str((submitted or {}).get("keyword") or "").strip().lower()
    question_type = str((submitted or {}).get("questionType") or "").strip()
    row = {
        "id": 990001,
        "questionId": 990001,
        "questionNo": 1,
        "questionType": "1",
        "questionTypeName": "鍗曢€夐",
        "title": "鏈湴闀滃儚閿欓绀轰緥",
        "questionContent": "鏈湴闀滃儚閿欓绀轰緥",
        "studentAnswer": "B",
        "rightAnswer": "A",
        "wrongCount": 1,
        "knowledgePointName": "Local Mirror Knowledge Point",
        "updatedTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    rows = [row]
    if keyword and keyword not in row["title"].lower():
        rows = []
    if question_type and question_type != row["questionType"]:
        rows = []
    start = (page_num - 1) * page_size
    page_rows = rows[start:start + page_size]
    total_size = len(rows)
    return {
        "pageNum": page_num,
        "pageSize": page_size,
        "totalSize": total_size,
        "totalPages": 0 if total_size == 0 else (total_size + page_size - 1) // page_size,
        "content": page_rows,
        "records": page_rows,
        "rows": page_rows,
        "list": page_rows,
        "totalContent": {
            "wrongQuestionCount": total_size,
            "questionCount": total_size,
        },
    }


def _build_competition_score_rank_rows(store: MirrorStore) -> list[dict[str, Any]]:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows: list[dict[str, Any]] = []
    for student in _competition_student_snapshots(store):
        rows.append(
            {
                "studentId": student["studentId"],
                "studentName": student["studentName"],
                "studentAccount": student["studentAccount"],
                "startTime": timestamp,
                "answerDuration": "00:08:00",
                "totalScore": 100,
                "rightNum": 1,
                "wrongNum": 0,
                "partiallyNum": 0,
                "submitTimes": 1,
                "status": "Submitted",
                "submitStatus": "Submitted",
                "passStatus": "鍙婃牸",
                "tchCheckDate": timestamp,
                "tch_check_date": timestamp,
                "tchComment": "Graded locally by the offline mirror.",
                "eduCampusId": student["campusId"],
            }
        )
    return rows


def _build_local_stuexam_question_list_content(
    store: MirrorStore,
    request: Request,
    request_body: bytes,
) -> dict[str, Any]:
    context = _local_stuexam_context(store, request, request_body)
    exam = _json_deep_copy(context["exam"])
    paper = _json_deep_copy(context["paper"])
    exam.setdefault("lasttime", exam.get("lasttime") or 3600)
    exam.setdefault("subject_id", _coerce_int(paper.get("subject_id")) or 2)
    exam.setdefault("title", paper.get("title") or exam.get("title") or "")
    return {
        "questionList": _json_deep_copy(context["questions"]),
        "exam": exam,
        "paper": paper,
        "stu_start_time": context["started_at"],
        "systeamDate": context["system_time"],
    }


def _build_local_stuexam_exam_list_content(
    store: MirrorStore,
    request: Request,
    request_body: bytes,
) -> dict[str, Any]:
    del request_body
    context = _local_stuexam_context(store, request)
    exam_rows = (
        (context["seed"].get("exam_list") or {}).get("content", {}).get("examList")
        if isinstance((context["seed"].get("exam_list") or {}).get("content"), dict)
        else []
    )
    rows = [_json_deep_copy(row) for row in exam_rows if isinstance(row, dict)]
    if not rows:
        rows = [_json_deep_copy(context["exam"])]
    return {
        "examList": rows,
        "dataList": rows,
        "list": rows,
        "total": len(rows),
        "page_no": 1,
        "page_size": max(len(rows), 1),
    }


def _build_local_stuexam_practice_list_content(
    store: MirrorStore,
    request: Request,
    request_body: bytes,
) -> dict[str, Any]:
    del request_body
    context = _local_stuexam_context(store, request)
    practice_rows = (
        (context["seed"].get("practice_list") or {}).get("content", {}).get("examList")
        if isinstance((context["seed"].get("practice_list") or {}).get("content"), dict)
        else []
    )
    rows = [_json_deep_copy(row) for row in practice_rows if isinstance(row, dict)]
    if not rows:
        rows = [_json_deep_copy(context["exam"])]
    return {
        "examList": rows,
        "dataList": rows,
        "list": rows,
        "total": len(rows),
        "page_no": 1,
        "page_size": max(len(rows), 1),
    }


def _build_local_stuexam_question_answer_content(
    store: MirrorStore,
    request: Request,
    request_body: bytes,
) -> dict[str, Any]:
    context = _local_stuexam_context(store, request, request_body)
    question_id = _parse_int_like(_request_payload_value(request, _load_request_payload(request_body), "questionId")) or context["question_id"]
    answer_row = store.get_local_student_exam_answer(
        context["exam_id"],
        question_id,
        stu_id=context["student_context"].get("student_id") or 0,
    )
    if answer_row is None:
        answer_row = {
            "stu_exam_question_id": context["exam_id"] * 100000 + question_id,
            "answer": "",
            "score": None,
        }
    return {
        "stuExamQuestion": {
            "id": answer_row.get("stu_exam_question_id"),
            "answer": answer_row.get("answer") or "",
            "score": answer_row.get("score"),
            "answer_state": "1",
        }
    }


def _submit_local_stuexam_answer(
    store: MirrorStore,
    request: Request,
    request_body: bytes,
) -> dict[str, Any]:
    context = _local_stuexam_context(store, request, request_body)
    submitted = _load_request_payload(request_body)
    question_id = _parse_int_like(_request_payload_value(request, submitted, "questionId")) or context["question_id"]
    question_score = _coerce_float_like(_request_payload_value(request, submitted, "questionScore"), 0.0)
    answer = str(_request_payload_value(request, submitted, "answer") or "")
    stu_exam_question_id = (
        _parse_int_like(_request_payload_value(request, submitted, "stuExamQuestionId"))
        or context["exam_id"] * 100000
        + question_id
    )
    submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    answer_row = store.upsert_local_student_exam_answer(
        context["exam_id"],
        question_id,
        {
            "stu_exam_question_id": stu_exam_question_id,
            "answer": answer,
            "question_score": question_score,
            "score": question_score,
            "submitted_at": submitted_at,
        },
        stu_id=context["student_context"].get("student_id") or 0,
    ) or {}
    store.upsert_local_student_exam_run(
        context["exam_id"],
        {
            "paper_id": context["paper"].get("id"),
            "title": context["exam"].get("title"),
            "started_at": context["started_at"],
        },
        stu_id=context["student_context"].get("student_id") or 0,
    )
    return {
        "is_create": True,
        "is_update": True,
        "stuExamQuestionId": answer_row.get("stu_exam_question_id") or stu_exam_question_id,
        "score": answer_row.get("score"),
    }


def _submit_local_stuexam_paper(
    store: MirrorStore,
    request: Request,
    request_body: bytes,
) -> dict[str, Any]:
    context = _local_stuexam_context(store, request, request_body)
    submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    store.upsert_local_student_exam_run(
        context["exam_id"],
        {
            "paper_id": context["paper"].get("id"),
            "title": context["exam"].get("title"),
            "started_at": context["started_at"],
            "submitted_at": submitted_at,
        },
        stu_id=context["student_context"].get("student_id") or 0,
    )
    answer_rows = store.list_local_student_exam_answers(
        context["exam_id"],
        stu_id=context["student_context"].get("student_id") or 0,
    )
    total_score = 0.0
    for row in answer_rows:
        total_score += float(row.get("score") or row.get("question_score") or 0)
    return {
        "is_submit": True,
        "is_create": True,
        "submitTime": submitted_at,
        "score": total_score,
    }


def _build_local_stuexam_result_question_list_content(
    store: MirrorStore,
    request: Request,
    request_body: bytes,
) -> dict[str, Any]:
    context = _local_stuexam_context(store, request, request_body)
    questions = _json_deep_copy(context["questions"])
    for question in questions:
        answer_info = question.get("stuExamQuestionInfo")
        if not isinstance(answer_info, dict):
            answer_info = {}
            question["stuExamQuestionInfo"] = answer_info
        answer_info.setdefault("answer_state", "1")
        answer_info.setdefault("score", question.get("score") or 0)
    return {
        "questionList": questions,
        "paperQuestionList": questions,
        "dataList": questions,
    }


def _build_local_stuexam_wrong_question_list_content(
    store: MirrorStore,
    request: Request,
    request_body: bytes,
) -> dict[str, Any]:
    context = _local_stuexam_context(store, request, request_body)
    rows: list[dict[str, Any]] = []
    for question in context["questions"]:
        rows.append(
            {
                "id": question.get("id"),
                "questionId": question.get("id"),
                "type": question.get("type"),
                "questionType": question.get("type"),
                "title": question.get("title_str") or re.sub(r"<[^>]+>", "", str(question.get("title") or "")),
                "rightAnswer": question.get("answer"),
                "studentAnswer": question.get("stu_answer") or "",
                "score": question.get("score") or 0,
                "stuExamQuestionInfo": question.get("stuExamQuestionInfo") or {"answer_state": "1"},
            }
        )
    return {
        "questionList": rows,
        "dataList": rows,
        "list": rows,
        "total": len(rows),
        "page_no": 1,
        "page_size": max(len(rows), 1),
    }


def _build_local_exam_check_paper_question_list_content(
    store: MirrorStore,
    request: Request,
    request_body: bytes,
) -> dict[str, Any]:
    context = _local_stuexam_context(store, request, request_body)
    rows: list[dict[str, Any]] = []
    for question in context["questions"]:
        question_info = _json_deep_copy(question)
        question_info["isShow"] = False
        rows.append(
            {
                "id": question.get("id"),
                "questionId": question.get("id"),
                "score": question.get("score") or 0,
                "questionInfo": question_info,
            }
        )
    return {
        "paperQuestionList": rows,
        "questionList": [_json_deep_copy(row["questionInfo"]) for row in rows],
    }


def _build_local_stu_practice_and_record_content(
    store: MirrorStore,
    request: Request,
    request_body: bytes,
) -> dict[str, Any]:
    context = _local_stuexam_context(store, request, request_body)
    run = store.get_local_student_exam_run(
        context["exam_id"],
        stu_id=context["student_context"].get("student_id") or 0,
    ) or {}
    answer_rows = store.list_local_student_exam_answers(
        context["exam_id"],
        stu_id=context["student_context"].get("student_id") or 0,
    )
    submitted_count = len([row for row in answer_rows if str(row.get("answer") or "").strip()])
    total_questions = len(context["questions"])
    row = {
        "id": context["exam_id"] * 10 + 1,
        "test_exam_id": context["exam_id"],
        "examId": context["exam_id"],
        "title": context["exam"].get("title") or "",
        "isRecord": 1,
        "start_time": run.get("started_at") or context["started_at"],
        "created_time": run.get("started_at") or context["started_at"],
        "last_time": max(submitted_count * 60, 60 if submitted_count else 0),
        "right_num": submitted_count,
        "wrong_num": max(total_questions - submitted_count, 0),
    }
    return {
        "dataList": [row],
        "list": [row],
        "total": 1,
    }


def _build_local_practice_record_question_list_content(
    store: MirrorStore,
    request: Request,
    request_body: bytes,
) -> dict[str, Any]:
    context = _local_stuexam_context(store, request, request_body)
    rows = _json_deep_copy(context["questions"])
    exam = _json_deep_copy(context["exam"])
    paper = _json_deep_copy(context["paper"])
    right_num = 0
    wrong_num = 0
    partially_num = 0

    for row in rows:
        answer_info = row.get("stuExamQuestionInfo")
        if not isinstance(answer_info, dict):
            continue
        answer_info.setdefault("score", row.get("score") or 0)
        state = str(answer_info.get("answer_state") or "")
        if state == "1":
            right_num += 1
        elif state == "2":
            wrong_num += 1
        elif state == "3":
            partially_num += 1

    exam.setdefault("id", context["exam_id"])
    exam.setdefault("title", paper.get("title") or exam.get("title") or "")
    exam.setdefault("is_show_answer", True)
    exam.setdefault("show_answer_type", 1)
    paper.setdefault("id", context["paper"].get("id"))
    paper.setdefault("title", exam.get("title") or "")
    return {
        "exam": exam,
        "paper": paper,
        "questionList": rows,
        "paperQuestionList": rows,
        "dataList": rows,
        "right_num": right_num,
        "wrong_num": wrong_num,
        "partially_num": partially_num,
        "realname": context["student_context"].get("display_name") or "",
    }


def _build_student_time_record_content(
    store: MirrorStore,
    request: Request,
    request_body: bytes,
) -> dict[str, Any]:
    submitted = _load_request_payload(request_body)
    page_num, page_size = _page_request_window(submitted, default_page_size=10)
    teacher_name = str(_teacher_user_info(store).get("realname") or _teacher_user_info(store).get("name") or "Local Mirror Teacher")
    active_minutes = 45
    if _parse_int_like(_request_payload_value(request, submitted, "numMin")) not in (None, 0):
        min_value = _parse_int_like(_request_payload_value(request, submitted, "numMin")) or 0
        if active_minutes < min_value:
            rows: list[dict[str, Any]] = []
        else:
            rows = []
    else:
        rows = []
    if not rows:
        rows = [
            {
                "id": 1,
                "userId": _parse_int_like(_request_payload_value(request, submitted, "userId")) or 0,
                "userName": teacher_name,
                "startTime": datetime.now().strftime("%Y-%m-%d 09:00:00"),
                "endTime": datetime.now().strftime("%Y-%m-%d 09:45:00"),
                "num": active_minutes,
                "studyNum": active_minutes,
                "activeNum": active_minutes,
                "remark": "鏈湴闀滃儚娲昏穬璁板綍",
                "createdTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        ]
    start = (page_num - 1) * page_size
    page_rows = rows[start:start + page_size]
    total_size = len(rows)
    return {
        "pageNum": page_num,
        "pageSize": page_size,
        "totalSize": total_size,
        "totalPages": 0 if total_size == 0 else (total_size + page_size - 1) // page_size,
        "content": page_rows,
        "records": page_rows,
        "rows": page_rows,
        "list": page_rows,
        "totalContent": {
            "recordCount": total_size,
            "totalMinute": sum(_coerce_int(row.get("num")) or 0 for row in rows),
        },
    }


def _build_educational_institution_info_content(store: MirrorStore) -> dict[str, Any]:
    school_info = _hydrate_teacher_school_info(store, _teacher_school_info(store))
    user_info = _hydrate_teacher_user_info(store, _teacher_user_info(store))
    campus_id = _teacher_primary_campus_id(store) or 0
    campus_name = _teacher_primary_campus_name(store)
    school_row = _json_deep_copy(school_info)
    school_row.setdefault("is_encryption", False)

    content = {
        "educational_institution_obj": [school_row],
        "educational_institution_closing_day_list": [],
        "educational_institution_class_day_list": [],
        "schoolInfo": school_row,
        "userInfo": _json_deep_copy(user_info),
        "eduCampusId": campus_id,
        "educational_institution_campus_id": campus_id,
        "educationalInstitutionCampusId": campus_id,
        "campusName": campus_name,
    }
    content.update({key: value for key, value in school_row.items() if key not in content})
    return content


def _build_user_campus_rows(store: MirrorStore, profile_name: str = "teacher") -> list[dict[str, Any]]:
    school_info = _hydrate_teacher_school_info(store, _teacher_school_info(store, profile_name), profile_name)
    user_info = _hydrate_teacher_user_info(store, _teacher_user_info(store, profile_name), profile_name)
    user_id = _teacher_admin_user_id(store, profile_name)
    campus_rows = store.list_user_campuses()
    rows: list[dict[str, Any]] = []

    for campus in campus_rows:
        if not isinstance(campus, dict):
            continue
        current = _json_deep_copy(campus)
        campus_id = _coerce_int(
            current.get("dept_id")
            or current.get("id")
            or current.get("eduCampusId")
            or current.get("campusId")
            or school_info.get("eduCampusId")
            or _teacher_primary_campus_id(store, profile_name)
        ) or 0
        campus_name = str(
            current.get("campusName")
            or current.get("dept_name")
            or current.get("name")
            or school_info.get("campusName")
            or school_info.get("name")
            or _teacher_primary_campus_name(store, profile_name)
            or "Default Campus"
        ).strip()
        current.setdefault("id", campus_id)
        current.setdefault("dept_id", campus_id)
        current.setdefault("eduCampusId", campus_id)
        current.setdefault("educationalInstitutionCampusId", campus_id)
        current.setdefault("educational_institution_campus_id", campus_id)
        current.setdefault("campusId", campus_id)
        current.setdefault("campusName", campus_name)
        current.setdefault("dept_name", campus_name)
        current.setdefault("name", campus_name)
        current.setdefault("user_id", user_id)
        if school_info.get("eduDomain") not in (None, ""):
            current.setdefault("eduDomain", school_info.get("eduDomain"))
        if user_info.get("realname") not in (None, ""):
            current.setdefault("userName", user_info.get("realname"))
        rows.append(current)

    if rows:
        return rows

    campus_id = _coerce_int(school_info.get("eduCampusId") or _teacher_primary_campus_id(store, profile_name)) or 0
    campus_name = str(
        school_info.get("campusName")
        or school_info.get("name")
        or _teacher_primary_campus_name(store, profile_name)
        or "Default Campus"
    ).strip()
    return [
        {
            "id": campus_id,
            "dept_id": campus_id,
            "eduCampusId": campus_id,
            "educationalInstitutionCampusId": campus_id,
            "educational_institution_campus_id": campus_id,
            "campusId": campus_id,
            "campusName": campus_name,
            "dept_name": campus_name,
            "name": campus_name,
            "user_id": user_id,
            "eduDomain": school_info.get("eduDomain") or school_info.get("domain") or "",
            "userName": user_info.get("realname") or user_info.get("realName") or user_info.get("name") or "",
        }
    ]


def _build_classroom_index_content(store: MirrorStore, request: Request) -> dict[str, Any]:
    resolved_profile = _resolve_profile(store, request)
    profile_name = resolved_profile["profile_name"] if resolved_profile else _resolve_profile_name(store, request)
    profile_role = _profile_role(profile_name, resolved_profile)
    if profile_role == "student":
        class_rows, user_subject = _build_student_class_rows(store, request)
    else:
        class_rows, user_subject = _build_teacher_class_rows(store, request)

    plan_rows = _build_teacher_teaching_plan_rows(store, request)
    plans_by_class: dict[int, list[dict[str, Any]]] = {}
    for plan in plan_rows:
        if not isinstance(plan, dict):
            continue
        class_info = plan.get("classInfo") if isinstance(plan.get("classInfo"), dict) else {}
        class_id = _coerce_int(class_info.get("id") or plan.get("curriculum_class_id") or plan.get("classId"))
        if class_id is None:
            continue
        plans_by_class.setdefault(class_id, []).append(_json_deep_copy(plan))

    page_limit = _coerce_int(_first_query_value(request, "pageLimit") or _first_query_value(request, "page_size")) or 20
    page_rows: list[dict[str, Any]] = []
    for row in class_rows[:page_limit]:
        normalized = _json_deep_copy(row)
        class_id = _coerce_int(normalized.get("id"))
        row_plans = plans_by_class.get(class_id or -1, [])
        normalized["tchPlanList"] = row_plans
        normalized["teachingPlanList"] = row_plans
        normalized["teaching_plan_list"] = row_plans
        normalized["tchPlanInfoList"] = row_plans
        if row_plans:
            normalized["recentTchPlanInfo"] = row_plans[0]
            normalized["nextTchPlanInfo"] = row_plans[-1]
        page_rows.append(normalized)

    visible_plan_rows = [
        plan
        for row in page_rows
        for plan in (row.get("tchPlanList") or [])
        if isinstance(plan, dict)
    ]
    return {
        "classList": page_rows,
        "classlist": page_rows,
        "tchClassList": page_rows,
        "classListWithTchPlanInfo": page_rows,
        "list": page_rows,
        "rows": page_rows,
        "userSubject": user_subject,
        "subjectList": user_subject,
        "tchPlanList": visible_plan_rows,
        "teachingPlanList": visible_plan_rows,
        "total": len(class_rows),
        "pageLimit": page_limit,
    }


def _teacher_notice_rows(store: MirrorStore) -> list[dict[str, Any]]:
    notice_rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for payload in store.load_api_payloads("teacher", "/api/get/tch/notice/list", method="GET"):
        content = payload.get("content") or {}
        entries = content.get("noticeUserList") or content.get("list") or []
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            notice_id = str(entry.get("id") or entry.get("notice_id") or "").strip()
            if notice_id and notice_id in seen_ids:
                continue
            if notice_id:
                seen_ids.add(notice_id)
            notice_rows.append(_json_deep_copy(entry))

    def sort_key(row: dict[str, Any]) -> tuple[str, int]:
        created_time = str(row.get("created_time") or row.get("createdTime") or "")
        notice_id = _coerce_int(row.get("id") or row.get("notice_id")) or 0
        return created_time, notice_id

    notice_rows.sort(key=sort_key, reverse=True)
    return notice_rows


def _build_recent_notice_content(store: MirrorStore) -> dict[str, Any]:
    for payload in store.load_api_payloads("teacher", "/api/getTchRecentNotReadNotice", method="GET"):
        content = payload.get("content")
        if isinstance(content, dict):
            normalized = _json_deep_copy(content)
            normalized.setdefault("notReadNotice", None)
            normalized.setdefault("notReadNum", 0)
            return normalized

    notice_rows = _teacher_notice_rows(store)
    fallback_not_read_num: int | None = None
    for payload in store.load_api_payloads("teacher", "/api/get/tch/notice/list", method="GET"):
        content = payload.get("content") or {}
        value = _parse_int_like(content.get("notReadNum"))
        if value is not None:
            fallback_not_read_num = value
            break
    unread_rows = [row for row in notice_rows if row.get("is_read") in (False, 0, "0")]
    latest_notice = unread_rows[0] if unread_rows else (notice_rows[0] if notice_rows else None)
    return {
        "notReadNotice": _json_deep_copy(latest_notice) if isinstance(latest_notice, dict) else None,
        "notReadNum": fallback_not_read_num if fallback_not_read_num is not None else len(unread_rows),
    }


def _build_school_notice_board_content(store: MirrorStore, request: Request) -> dict[str, Any]:
    page_no_raw = _first_query_value(request, "page_no") or "1"
    page_size_raw = _first_query_value(request, "page_size") or "3"
    page_no = int(page_no_raw) if page_no_raw.isdigit() else 1
    page_size = int(page_size_raw) if page_size_raw.isdigit() else 3
    page_no = max(page_no, 1)
    page_size = max(page_size, 1)

    rows = _teacher_notice_rows(store)
    start = (page_no - 1) * page_size
    page_rows = rows[start:start + page_size]
    recent_notice = _build_recent_notice_content(store)
    total_size = len(rows)
    return {
        "noticeUserList": page_rows,
        "notReadNum": _parse_int_like(recent_notice.get("notReadNum")) or 0,
        "page_no": page_no,
        "page_size": page_size,
        "pageNum": page_no,
        "pageSize": page_size,
        "total": total_size,
        "totalSize": total_size,
        "totalPages": 0 if total_size == 0 else (total_size + page_size - 1) // page_size,
    }


def _build_visit_record_content(store: MirrorStore, request: Request, request_body: bytes) -> dict[str, Any]:
    del store
    submitted = _load_request_payload(request_body)
    page_num, page_size = _page_request_window(submitted, default_page_size=10)
    page_num = max(page_num, 1)
    page_size = max(page_size, 1)
    return _empty_page_request_content(
        page_num,
        page_size,
        extra={
            "pageRequest": {"pageNum": page_num, "pageSize": page_size},
            "totalContent": {"recordCount": 0},
        },
    )


def _build_admin_curriculum_rows(store: MirrorStore, request: Request) -> list[dict[str, Any]]:
    subject_id = _first_query_value(request, "subject_id")
    teaching_type = _first_query_value(request, "teaching_type")
    curriculum_type = _first_query_value(request, "curriculum_type")
    check_state = _first_query_value(request, "check_state")
    subject_name_map = _teacher_subject_name_map(store)

    rows: list[dict[str, Any]] = []
    for entry in store.list_campus_curriculum_auths():
        if not isinstance(entry, dict):
            continue
        row = _curriculum_row_from_auth_entry(store, entry, subject_name_map)
        if row is None:
            continue
        _normalize_curriculum_storage_fields(row)
        row.pop("subject_name", None)
        if "check_state" not in row or row.get("check_state") in (None, ""):
            row["check_state"] = entry.get("check_state")

        if subject_id and str(row.get("subject_id") or "") != subject_id:
            continue
        if teaching_type and str(row.get("teaching_type") or "") != teaching_type:
            continue
        if curriculum_type and str(row.get("curriculum_type") or "") != curriculum_type:
            continue
        if check_state:
            row_check_state = row.get("check_state")
            if row_check_state not in (None, "") and str(row_check_state) != check_state:
                continue

        rows.append(row)

    return rows


def _build_admin_curriculum_detail_content(store: MirrorStore, request: Request) -> dict[str, Any]:
    curriculum_id = _coerce_int(
        _first_query_value(request, "curriculum_id")
        or _first_query_value(request, "id")
    )
    if curriculum_id is None:
        return {
            "curriculum": [],
            "curriculum_material_list": [],
            "curriculumMaterialList": [],
            "currculumMaterialList": [],
        }

    matching_row: dict[str, Any] | None = None
    for row in _build_teacher_curriculum_rows(store, request):
        if _coerce_int(row.get("id")) == curriculum_id:
            matching_row = _json_deep_copy(row)
            break

    if matching_row is None:
        subject_name_map = _teacher_subject_name_map(store)
        for entry in store.list_campus_curriculum_auths():
            if not isinstance(entry, dict):
                continue
            curriculum_info = entry.get("curriculumInfo") or {}
            if _coerce_int((curriculum_info or {}).get("id") or entry.get("curriculum_id") or entry.get("id")) != curriculum_id:
                continue
            row = _curriculum_row_from_auth_entry(store, entry, subject_name_map)
            if row is None:
                continue
            _normalize_curriculum_storage_fields(row)
            matching_row = row
            break

    if matching_row is None:
        return {
            "curriculum": [],
            "curriculum_material_list": [],
            "curriculumMaterialList": [],
            "currculumMaterialList": [],
        }

    material_rows = matching_row.get("curriculumMaterialList")
    if not isinstance(material_rows, list):
        material_rows = _curriculum_materials_by_curriculum(store).get(curriculum_id, [])
    material_rows = _json_deep_copy(material_rows)

    curriculum_row = _json_deep_copy(matching_row)
    curriculum_row["curriculum_id"] = curriculum_id
    curriculum_row["curriculum_data_url"] = curriculum_row.get("curriculum_data_url") or "[]"
    curriculum_row["curriculumDataUrl"] = curriculum_row["curriculum_data_url"]
    curriculum_row["curriculum_classes_list"] = material_rows
    curriculum_row["curriculumClassesList"] = _json_deep_copy(material_rows)

    return {
        "curriculum": [curriculum_row],
        "curriculum_material_list": material_rows,
        "curriculumMaterialList": _json_deep_copy(material_rows),
        "currculumMaterialList": _json_deep_copy(material_rows),
    }


def _build_local_student_entry(student: dict[str, Any], store: MirrorStore) -> dict[str, Any]:
    teacher_profile = store.get_profile("teacher") or {}
    school_info = (teacher_profile.get("fresh_auth") or {}).get("schoolInfo") or {}
    campus_name = school_info.get("campusName") or school_info.get("name") or "榛樿鏍″尯"
    school_domain = school_info.get("eduDomain") or school_info.get("domain") or ""
    enddate = student.get("study_date") or ""
    if enddate and len(enddate) == 10:
        enddate = f"{enddate} 23:59:59"
    display_name = _student_display_name(student, default_id=student.get("id"))
    entry = {
        "id": student["id"],
        "name": student["name"],
        "normal_state": student["normal_state"],
        "class_str": "--",
        "campusName": campus_name,
        "schoolName": student["school_name"] or campus_name,
        "schoolDomain": school_domain,
        "enddate": enddate,
        "studentUserInfo": {
            "id": student["id"],
            "realname": display_name,
            "sex": student["sex"],
            "phone_num": student["phone_num"],
            "school_name": student["school_name"],
            "grade": student["grade"],
            "headimg_url": student["headimg_url"],
        },
        "stuClassArr": [],
    }
    return _apply_student_overlay_to_row(entry, store.get_student_overlay(student["id"]))


def _build_local_select_study_entry(student: dict[str, Any], store: MirrorStore) -> dict[str, Any]:
    teacher_profile = store.get_profile("teacher") or {}
    school_info = (teacher_profile.get("fresh_auth") or {}).get("schoolInfo") or {}
    campus_name = school_info.get("campusName") or school_info.get("name") or "姒涙顓婚弽鈥冲隘"
    display_name = _student_display_name(student, default_id=student.get("id"))
    row = {
        "stuId": student["id"],
        "stuName": display_name,
        "normalState": int(student["normal_state"]) if str(student["normal_state"]).isdigit() else 1,
        "stuAccount": student["name"],
        "className": "--",
        "openId": None,
        "authorizerOpenid": None,
        "parentWeChat": DEFAULT_UNBOUND_TEXT,
        "wcmFlag": DEFAULT_UNBOUND_TEXT,
        "endDate": student["study_date"],
        "eduCampusName": campus_name,
        "sex": student["sex"],
        "age": None,
        "birthday": None,
        "kinship": None,
        "phoneNum": student["phone_num"],
        "contactInformation": None,
        "schoolName": student["school_name"],
        "grade": student["grade"] or None,
        "leader": None,
        "leaderName": student["leader"] or "",
        "createdTime": student["created_time"],
        "activeStatus": False,
        "totalActiveTime": 0,
    }
    return _apply_student_overlay_to_row(row, store.get_student_overlay(student["id"]))


def _build_historical_select_study_entry(store: MirrorStore, stu_id: int) -> dict[str, Any]:
    overlay = store.get_student_overlay(stu_id)
    for student in store.list_local_students():
        if student["id"] == stu_id:
            return _build_local_select_study_entry(student, store)

    cached = store.find_cached_student_row(stu_id)
    if isinstance(cached, dict):
        return _apply_student_overlay_to_row(cached, overlay)

    fallback = _build_local_student_auth_content(stu_id, overlay)
    fallback.update(
        {
            "stuName": f"Mirror Student {stu_id}",
            "stuAccount": f"mirror-stu-{stu_id}",
            "className": "--",
            "endDate": "",
            "eduCampusName": "",
            "sex": "",
            "age": None,
            "birthday": None,
            "kinship": None,
            "phoneNum": "",
            "contactInformation": None,
            "schoolName": "",
            "grade": None,
            "leader": None,
            "leaderName": "",
            "createdTime": "",
            "activeStatus": False,
            "totalActiveTime": 0,
        }
    )
    return fallback


def _build_select_study_entry_from_cached_student_row(store: MirrorStore, row: dict[str, Any]) -> dict[str, Any]:
    student_info = row.get("studentUserInfo") if isinstance(row.get("studentUserInfo"), dict) else {}
    class_rows = row.get("stuClassArr") if isinstance(row.get("stuClassArr"), list) else []
    class_names: list[str] = []
    for class_row in class_rows:
        if not isinstance(class_row, dict):
            continue
        class_name = (
            class_row.get("className")
            or ((class_row.get("classInfo") or {}).get("name") if isinstance(class_row.get("classInfo"), dict) else None)
            or ""
        )
        class_name = str(class_name or "").strip()
        if class_name and class_name not in class_names:
            class_names.append(class_name)

    normalized_row = {
        "stuId": _coerce_int(row.get("id")) or 0,
        "stuName": str(student_info.get("realname") or row.get("realname") or row.get("name") or "").strip(),
        "normalState": _coerce_int(row.get("normal_state")) or _coerce_int(row.get("normalState")) or 1,
        "stuAccount": str(row.get("name") or "").strip(),
        "className": " , ".join(class_names) if class_names else str(row.get("class_str") or "--"),
        "openId": row.get("openId"),
        "authorizerOpenid": row.get("authorizerOpenid"),
        "parentWeChat": row.get("parentWeChat") or DEFAULT_UNBOUND_TEXT,
        "wcmFlag": row.get("wcmFlag") or DEFAULT_UNBOUND_TEXT,
        "endDate": (
            str(row.get("endDate") or row.get("enddate") or "").strip()[:10]
            or str(row.get("study_date") or "").strip()[:10]
        ),
        "eduCampusName": str(row.get("campusName") or _teacher_primary_campus_name(store) or "").strip(),
        "sex": str(student_info.get("sex") or row.get("sex") or "").strip(),
        "age": None,
        "birthday": student_info.get("birthday"),
        "kinship": None,
        "phoneNum": str(student_info.get("phone_num") or row.get("phone_num") or "").strip(),
        "contactInformation": None,
        "schoolName": str(student_info.get("school_name") or row.get("schoolName") or "").strip(),
        "grade": student_info.get("grade") or None,
        "leader": student_info.get("leader"),
        "leaderName": student_info.get("leaderName") or row.get("leaderName") or "",
        "createdTime": str(row.get("created_time") or row.get("createdTime") or "").strip(),
        "activeStatus": False,
        "totalActiveTime": 0,
    }
    return _apply_student_overlay_to_row(normalized_row, store.get_student_overlay(normalized_row["stuId"]))


def _cached_campus_user_row_looks_like_student(row: dict[str, Any]) -> bool:
    if any(
        bool(row.get(key))
        for key in (
            "is_platform_tch",
            "is_edu_tch",
            "is_super_administrator",
            "is_principal",
            "tch_jiaoyan_auth",
            "tch_shizi_auth",
            "tch_shixun_auth",
            "tch_ktsl_auth",
            "tch_kftd_auth",
            "notice_auth",
        )
    ):
        return False
    return any(
        key in row and row.get(key) not in (None, "", [], {})
        for key in (
            "stuId",
            "studentId",
            "studentUserInfo",
            "stuAccount",
            "normalState",
            "normal_state",
            "stuClassArr",
            "class_str",
            "className",
            "zone_auth",
            "oj_auth",
            "p_auth",
            "enddate",
            "endDate",
        )
    )


def _build_select_study_rows(store: MirrorStore) -> list[dict[str, Any]]:
    rows_by_stu_id: dict[int, dict[str, Any]] = {}
    for student in store.list_local_students():
        student_id = _coerce_int(student.get("id"))
        if student_id is None:
            continue
        overlay = store.get_student_overlay(student_id)
        if _student_overlay_is_hidden(overlay):
            continue
        rows_by_stu_id[student_id] = _build_local_select_study_entry(student, store)

    # Performance guard: skip the expensive cached-body scan when we already have
    # local students to surface. Audit/historical student overlays are preserved
    # separately by the historical endpoints and are not needed for day-to-day teacher
    # workflows (adding students to a class, etc.).
    if not rows_by_stu_id:
        for student in store.list_campus_user_students():
            if not isinstance(student, dict):
                continue
            if not _cached_campus_user_row_looks_like_student(student):
                continue
            student_id = _coerce_int(student.get("id") or student.get("stuId") or student.get("studentId"))
            if student_id is None or student_id in rows_by_stu_id:
                continue
            overlay = store.get_student_overlay(student_id)
            if _student_overlay_is_hidden(overlay):
                continue
            rows_by_stu_id[student_id] = _build_select_study_entry_from_cached_student_row(store, student)

    return sorted(
        rows_by_stu_id.values(),
        key=lambda row: (
            str(row.get("createdTime") or ""),
            _coerce_int(row.get("stuId")) or 0,
        ),
        reverse=True,
    )


def _historical_student_ids(store: MirrorStore, existing_rows: list[Any] | None = None) -> list[int]:
    historical_ids = set(store.list_historical_student_ids())
    if isinstance(existing_rows, list):
        for row in existing_rows:
            if not isinstance(row, dict):
                continue
            stu_id = _student_row_id(row)
            if stu_id is None:
                continue
            overlay = store.get_student_overlay(stu_id)
            if _student_overlay_is_historical(overlay):
                historical_ids.add(stu_id)
    return sorted(historical_ids, reverse=True)


def _normalize_student_fresh_data_content(store: MirrorStore, content: dict[str, Any] | None) -> dict[str, Any]:
    normalized = _json_deep_copy(content or {}) if isinstance(content, dict) else {}
    student_profile = store.get_profile("student") or {}
    profile_fresh_auth = student_profile.get("fresh_auth") or {}

    for key in ("identity", "userInfo", "schoolInfo", "roleList"):
        if normalized.get(key) in (None, "") and profile_fresh_auth.get(key) not in (None, ""):
            normalized[key] = _json_deep_copy(profile_fresh_auth[key])

    user_info = normalized.get("userInfo")
    if not isinstance(user_info, dict):
        user_info = {}
    normalized["userInfo"] = _merge_dict_defaults(user_info, _build_student_homepage_user_info(store, request))
    user_info = normalized["userInfo"]

    school_info = normalized.get("schoolInfo")
    school_source = school_info if isinstance(school_info, dict) else (profile_fresh_auth.get("schoolInfo") or {})
    normalized["schoolInfo"] = _hydrate_teacher_school_info(store, school_source, "student")

    stu_user_info = user_info.get("stuUserInfo")
    if isinstance(stu_user_info, dict):
        normalized.setdefault("stuUserInfo", _json_deep_copy(stu_user_info))
        nested_stu_user_info = stu_user_info.get("stuUserInfo")
        if isinstance(nested_stu_user_info, dict):
            normalized.setdefault("stuBaseInfo", _json_deep_copy(nested_stu_user_info))

    return normalized


def _merge_local_students_into_payload(store: MirrorStore, request: Request, payload: dict[str, Any]) -> dict[str, Any]:
    path = request.url.path
    content = payload.get("content")
    if not isinstance(content, dict):
        return payload

    if path == "/java-api/student/stu/freshData":
        payload["content"] = _normalize_student_fresh_data_content(store, content)
        return payload

    if path == "/api/get/campus/user/list":
        campus_id = _first_query_value(request, "campusId")
        existing = content.get("campusUserList")
        if existing is None:
            local_students = []
            for student in store.list_local_students(campus_id):
                overlay = store.get_student_overlay(student["id"])
                if _student_overlay_is_hidden(overlay):
                    continue
                local_students.append(_build_local_student_entry(student, store))
            if not local_students:
                return payload
            content["campusUserList"] = local_students
            return payload

        merged: list[Any] = []
        for student in store.list_local_students(campus_id):
            overlay = store.get_student_overlay(student["id"])
            if _student_overlay_is_hidden(overlay):
                continue
            merged.append(_build_local_student_entry(student, store))
        existing_rows = existing or []
        if isinstance(existing_rows, list):
            for row in existing_rows:
                if not isinstance(row, dict):
                    merged.append(row)
                    continue
                overlay = store.get_student_overlay(_student_row_id(row))
                if _student_overlay_is_hidden(overlay):
                    continue
                merged.append(_apply_student_overlay_to_row(row, overlay))
        content["campusUserList"] = merged
        return payload

    if path == "/java-api/school/getStudentList":
        merged: list[Any] = []
        local_count = 0
        for student in store.list_local_students():
            overlay = store.get_student_overlay(student["id"])
            if _student_overlay_is_hidden(overlay):
                continue
            merged.append(_build_local_student_entry(student, store))
            local_count += 1
        existing = content.get("studentList") or []
        removed_existing = 0
        if isinstance(existing, list):
            for row in existing:
                if not isinstance(row, dict):
                    merged.append(row)
                    continue
                overlay = store.get_student_overlay(_student_row_id(row))
                if _student_overlay_is_hidden(overlay):
                    removed_existing += 1
                    continue
                merged.append(_apply_student_overlay_to_row(row, overlay))
        content["studentList"] = merged
        original_total = content.get("total")
        total_value = _parse_int_like(original_total)
        if total_value is None:
            content["total"] = len(merged)
        else:
            content["total"] = _format_total_like(original_total, max(total_value - removed_existing, 0) + local_count)
        return payload

    if path == "/java-api/school/stu/selectStudy":
        rows: list[Any] = []
        local_count = 0
        local_student_ids: set[int] = set()
        for student in store.list_local_students():
            overlay = store.get_student_overlay(student["id"])
            if _student_overlay_is_hidden(overlay):
                continue
            rows.append(_build_local_select_study_entry(student, store))
            local_count += 1
            local_student_ids.add(student["id"])
        existing = content.get("content") or []
        removed_existing = 0
        replaced_existing = 0
        if isinstance(existing, list):
            for row in existing:
                if not isinstance(row, dict):
                    rows.append(row)
                    continue
                student_id = _student_row_id(row)
                if student_id in local_student_ids:
                    replaced_existing += 1
                    continue
                overlay = store.get_student_overlay(student_id)
                if _student_overlay_is_hidden(overlay):
                    removed_existing += 1
                    continue
                rows.append(_apply_student_overlay_to_row(row, overlay))
        content["content"] = rows
        original_total_size = content.get("totalSize")
        total_size_value = _parse_int_like(original_total_size)
        total_size = (
            len(rows)
            if total_size_value is None
            else max(total_size_value - removed_existing - replaced_existing, 0) + local_count
        )
        content["totalSize"] = _format_total_like(original_total_size, total_size)
        page_size = _parse_int_like(content.get("pageSize")) or len(rows) or 1
        content["totalPages"] = 0 if total_size == 0 else (total_size + page_size - 1) // page_size
        return payload

    if path == "/java-api/school/stu/selectStuOut":
        existing = content.get("content") or []
        rows: list[Any] = []
        seen_ids: set[int] = set()
        removed_existing = 0
        if isinstance(existing, list):
            for row in existing:
                if not isinstance(row, dict):
                    rows.append(row)
                    continue
                row_id = _student_row_id(row)
                overlay = store.get_student_overlay(row_id)
                if overlay is None:
                    rows.append(row)
                    if row_id is not None:
                        seen_ids.add(row_id)
                    continue
                if _student_overlay_is_historical(overlay):
                    rows.append(_apply_student_overlay_to_row(row, overlay))
                    if row_id is not None:
                        seen_ids.add(row_id)
                    continue
                # Hide stale upstream rows once a student has been restored or deleted locally.
                removed_existing += 1

        added_count = 0
        for stu_id in _historical_student_ids(store, existing if isinstance(existing, list) else None):
            if stu_id in seen_ids:
                continue
            rows.append(_build_historical_select_study_entry(store, stu_id))
            seen_ids.add(stu_id)
            added_count += 1

        content["content"] = rows
        original_total_size = content.get("totalSize")
        total_size_value = _parse_int_like(original_total_size)
        total_size = len(rows) if total_size_value is None else max(total_size_value - removed_existing, 0) + added_count
        content["totalSize"] = _format_total_like(original_total_size, total_size)
        page_size = _parse_int_like(content.get("pageSize")) or len(rows) or 1
        content["totalPages"] = 0 if total_size == 0 else (total_size + page_size - 1) // page_size
        return payload

    if path == "/java-api/school/stu/queryClsStuMsg" and isinstance(content, dict):
        overlay = store.get_student_overlay(_student_row_id(content))
        payload["content"] = _apply_student_overlay_to_row(content, overlay)
        return payload

    if path == "/java-api/school/stu/selectStudy":
        local_students = store.list_local_students()
        if not local_students:
            return payload
        rows = []
        for student in local_students:
            rows.append(
                {
                    "stuId": student["id"],
                    "stuName": _student_display_name(student, default_id=student.get("id")),
                    "normalState": int(student["normal_state"]) if str(student["normal_state"]).isdigit() else 1,
                    "stuAccount": student["name"],
                    "className": "--",
                    "openId": None,
                    "authorizerOpenid": None,
                    "parentWeChat": "Unbound",
                    "wcmFlag": "Unbound",
                    "endDate": student["study_date"],
                    "eduCampusName": "榛樿鏍″尯",
                    "sex": student["sex"],
                    "age": None,
                    "birthday": None,
                    "kinship": None,
                    "phoneNum": student["phone_num"],
                    "contactInformation": None,
                    "schoolName": student["school_name"],
                    "grade": student["grade"] or None,
                    "leader": None,
                    "leaderName": student["leader"] or "",
                    "createdTime": student["created_time"],
                    "activeStatus": False,
                    "totalActiveTime": 0,
                }
            )
        existing = content.get("content") or []
        if isinstance(existing, list):
            rows.extend(existing)
        content["content"] = rows
        total_size = content.get("totalSize")
        if isinstance(total_size, int):
            content["totalSize"] = total_size + len(local_students)
        elif isinstance(total_size, str) and total_size.isdigit():
            content["totalSize"] = str(int(total_size) + len(local_students))
        return payload

    return payload


def _build_local_api_fallback(store: MirrorStore, request: Request, request_body: bytes) -> dict[str, Any] | None:
    path = request.url.path
    normalized_path = re.sub(r"/{2,}", "/", path)
    if path == "/api/admin/fresh/auth/user/data":
        resolved_profile = _resolve_profile(store, request)
        teacher_profile_name = (
            resolved_profile["profile_name"]
            if resolved_profile is not None and resolved_profile.get("profile_name")
            else "teacher"
        )
        teacher_profile = store.get_profile(teacher_profile_name) or store.get_profile("teacher") or {}
        teacher_user_info = (teacher_profile.get("fresh_auth") or {}).get("userInfo") or {}
        auth_user_permission = _teacher_admin_permissions(store, teacher_profile_name)
        payload = {
            "success": True,
            "content": {
                "token": teacher_profile.get("token") or "",
                "userId": _teacher_admin_user_id(store, teacher_profile_name),
                "userName": teacher_profile.get("username") or "",
                "userRealname": teacher_user_info.get("realname")
                or teacher_user_info.get("realName")
                or teacher_user_info.get("userRealname")
                or teacher_profile.get("username")
                or "",
                "authUserPermission": auth_user_permission,
            },
            "error": {"message": "", "code": ""},
        }
        return {
            "status": 200,
            "content_type": "application/json; charset=utf-8",
            "headers": {"content-type": "application/json; charset=utf-8"},
            "body": json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        }

    if path == "/api/get/user/info/by/user/code":
        teacher_profile = store.get_profile("teacher") or {}
        teacher_fresh_auth = teacher_profile.get("fresh_auth") or {}
        teacher_user_info = teacher_fresh_auth.get("userInfo") or {}
        teacher_school_info = teacher_fresh_auth.get("schoolInfo") or {}
        username = (
            teacher_user_info.get("username")
            or teacher_user_info.get("realName")
            or teacher_user_info.get("realname")
            or teacher_user_info.get("userRealname")
            or teacher_profile.get("username")
            or ""
        )
        domain = (
            teacher_school_info.get("domain")
            or teacher_school_info.get("eduDomain")
            or teacher_school_info.get("name")
            or "steam.fun"
        )
        payload = {
            "success": True,
            "content": {
                "username": username,
                "domain": domain,
            },
            "error": {"message": "", "code": ""},
        }
        return {
            "status": 200,
            "content_type": "application/json; charset=utf-8",
            "headers": {"content-type": "application/json; charset=utf-8"},
            "body": json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        }

    if path == "/api/get/user/campus/list":
        resolved_profile = _resolve_profile(store, request)
        profile_name = (
            resolved_profile["profile_name"]
            if resolved_profile is not None and resolved_profile.get("profile_name")
            else _resolve_profile_name(store, request)
            or "teacher"
        )
        rows = _build_user_campus_rows(store, profile_name)
        return _local_json_record(
            _success_payload(
                {
                    "campusList": rows,
                    "userCampusList": rows,
                    "userDeptList": rows,
                    "campus_list": rows,
                    "list": rows,
                    "rows": rows,
                    "total": len(rows),
                }
            )
        )

    if path == "/api/get/educational_institution_campus/list":
        resolved_profile = _resolve_profile(store, request)
        profile_name = (
            resolved_profile["profile_name"]
            if resolved_profile is not None and resolved_profile.get("profile_name")
            else _resolve_profile_name(store, request)
            or "teacher"
        )
        rows = _build_user_campus_rows(store, profile_name)
        return _local_json_record(
            _success_payload(
                {
                    "campusList": rows,
                    "educationalInstitutionCampusList": rows,
                    "educational_institution_campus_list": rows,
                    "userCampusList": rows,
                    "userDeptList": rows,
                    "list": rows,
                    "rows": rows,
                    "total": len(rows),
                }
            )
        )

    if path == "/api/get/campus/arr/subject/list":
        subjects = _teacher_subject_catalog(store)
        return _local_json_record(
            _success_payload(
                {
                    "campusSubjectList": subjects,
                    "subjectList": subjects,
                    "schoolSubjectList": subjects,
                    "userSubject": subjects,
                    "list": subjects,
                    "rows": subjects,
                    "total": len(subjects),
                }
            )
        )

    if path == "/api/get/campus/user/list":
        campus_id = _first_query_value(request, "campusId")
        rows = [
            _build_local_student_entry(student, store)
            for student in store.list_local_students(campus_id)
            if not _student_overlay_is_hidden(store.get_student_overlay(student["id"]))
        ]
        return _local_json_record(
            _success_payload(
                {
                    "campusUserList": rows,
                    "userList": rows,
                    "studentList": rows,
                    "list": rows,
                    "rows": rows,
                    "total": len(rows),
                    "page_no": _page_window(request)[0],
                    "page_size": _page_window(request)[1],
                }
            )
        )

    if path == "/java-api/school/tch/verifyPhoneState":
        return _local_json_record(_success_payload(0))

    if path == "/java-api/school/tch/checkPwd":
        return _local_json_record(_success_payload(False))

    if path == "/api/tch/get/tch/subject/auth":
        resolved_profile = _resolve_profile(store, request)
        profile_name = resolved_profile["profile_name"] if resolved_profile else _resolve_profile_name(store, request)
        profile_role = _profile_role(profile_name, resolved_profile)
        subjects = _student_subject_rows(store) if profile_role == "student" else _teacher_subject_catalog(store)
        return _local_json_record(
            _success_payload(
                {
                    "subjectList": subjects,
                    "userSubject": subjects,
                    "tchSubjectList": subjects,
                    "stuSubjectList": subjects,
                    "list": subjects,
                    "rows": subjects,
                    "total": len(subjects),
                }
            )
        )

    if path == "/api/tch/getTchIndexClassListWithTchPlanInfo":
        return _local_json_record(_success_payload(_build_classroom_index_content(store, request)))

    if path == "/java-api/auth/sch/eduRole/queryListNoCheck":
        return _local_json_record(_success_payload(_json_deep_copy(_local_staff_role_rows())))

    if normalized_path == "/java-api/school/tch/employeeSetting/selectEmployList":
        submitted = _load_request_payload(request_body)
        page_num, page_size = _page_request_window(submitted, default_page_size=20)
        query = str(
            _request_payload_value(request, submitted, "keyword", "query", "name", "realName") or ""
        ).strip().lower()
        rows = _staff_account_rows(store, include_admin=False, include_subjects=True)
        if query:
            rows = [
                row
                for row in rows
                if query in str(row.get("name") or "").lower()
                or query in str(row.get("realName") or "").lower()
            ]
        start = (page_num - 1) * page_size
        page_rows = rows[start:start + page_size]
        return _local_json_record(
            _success_payload(
                {
                    "pageNum": page_num,
                    "pageSize": page_size,
                    "total": len(rows),
                    "totalSize": len(rows),
                    "records": page_rows,
                    "content": page_rows,
                    "rows": page_rows,
                    "list": page_rows,
                }
            )
        )

    if path == "/api/get/school/right/info":
        campuses = store.list_campuses()
        return _local_json_record(
            _success_payload(
                {
                    "campusList": campuses,
                    "eduCampusList": campuses,
                    "list": campuses,
                    "rows": campuses,
                }
            )
        )

    if path == "/java-api/school/edu/campus/selectEduCampusTchList":
        requested_campus_ids = _extract_campus_ids(
            _request_payload_value(request, _load_request_payload(request_body), "eduCampusId", "campusId")
        )
        rows = _staff_account_rows(store, include_admin=False)
        if requested_campus_ids:
            allowed = set(requested_campus_ids)
            rows = [
                row
                for row in rows
                if allowed.intersection(_extract_campus_ids(row.get("eduCampusIdList") or row.get("eduCampusId")))
            ]
        return _local_json_record(_success_payload(rows))

    if path == "/api/admin/get/auth/user/list":
        submitted = _load_request_payload(request_body)
        page_num, page_size = _page_request_window(submitted, default_page_size=10)
        requested_campus_ids = _extract_campus_ids((submitted or {}).get("eduCampusId") if isinstance(submitted, dict) else None)
        requested_role_ids = _extract_int_list((submitted or {}).get("roleId") if isinstance(submitted, dict) else None)
        name_filter = str((submitted or {}).get("name") or "").strip().lower() if isinstance(submitted, dict) else ""
        real_name_filter = str((submitted or {}).get("realName") or "").strip().lower() if isinstance(submitted, dict) else ""
        phone_filter = str((submitted or {}).get("phoneNum") or "").strip().lower() if isinstance(submitted, dict) else ""
        state_filter = _normalized_optional_filter_text((submitted or {}).get("state") if isinstance(submitted, dict) else "").lower()
        rows: list[dict[str, Any]] = []
        for row in _staff_account_rows(store, include_admin=True):
            row_campus_ids = _extract_campus_ids(row.get("eduCampusIdList") or row.get("eduCampusId"))
            row_role_ids = _extract_int_list(row.get("eduRoleIdList") or row.get("roleIdList"))
            if requested_campus_ids and not set(requested_campus_ids).intersection(row_campus_ids):
                continue
            if requested_role_ids and not set(requested_role_ids).intersection(row_role_ids):
                continue
            if name_filter and name_filter not in str(row.get("name") or "").lower():
                continue
            if real_name_filter and real_name_filter not in str(row.get("realName") or "").lower():
                continue
            if phone_filter and phone_filter not in str(row.get("phoneNum") or "").lower():
                continue
            if state_filter and state_filter not in str(row.get("state") or "").lower():
                continue
            rows.append(row)
        start = (page_num - 1) * page_size
        page_rows = rows[start:start + page_size]
        total_size = len(rows)
        return _local_json_record(
            _success_payload(
                {
                    "pageNum": page_num,
                    "pageSize": page_size,
                    "totalSize": total_size,
                    "totalPages": 0 if total_size == 0 else (total_size + page_size - 1) // page_size,
                    "content": page_rows,
                    "records": page_rows,
                    "rows": page_rows,
                    "list": page_rows,
                    "total": total_size,
                }
            )
        )

    if path == "/api/admin/get/auth/user/info":
        submitted = _load_request_payload(request_body)
        requested_user_id = _parse_int_like(_request_payload_value(request, submitted, "userId", "id"))
        requested_username = str(
            _request_payload_value(request, submitted, "name", "userName", "username") or ""
        ).strip()
        profile = _find_staff_profile(
            store,
            user_id=requested_user_id,
            username=requested_username,
            include_admin=True,
        )
        detail = _staff_account_row(store, profile or {}, include_subjects=True) if profile is not None else {}
        return _local_json_record(_success_payload(detail))

    if path == "/api/admin/add/or/update/auth/user":
        submitted = _load_request_payload(request_body)
        if not isinstance(submitted, dict):
            submitted = {}
        stored_profile = _upsert_staff_account_profile(store, request, submitted)
        return _local_json_record(_success_payload(_staff_account_row(store, stored_profile, include_subjects=True)))

    if path == "/api/admin/delete/auth/user":
        submitted = _load_request_payload(request_body)
        requested_user_id = _parse_int_like(_request_payload_value(request, submitted, "userId", "id"))
        requested_username = str(
            _request_payload_value(request, submitted, "name", "userName", "username") or ""
        ).strip()
        profile = _find_staff_profile(
            store,
            user_id=requested_user_id,
            username=requested_username,
            include_admin=True,
        )
        deleted = False
        if profile is not None:
            profile_name = str(profile.get("profile_name") or "").strip()
            if profile_name not in {"teacher", "admin", "student"}:
                deleted = store.delete_profile(profile_name)
        return _local_json_record(_success_payload({"is_delete": deleted}))

    if path == "/api/admin/auth/user/update/password":
        submitted = _load_request_payload(request_body)
        requested_user_id = _parse_int_like(_request_payload_value(request, submitted, "userId", "id"))
        profile = _find_staff_profile(store, user_id=requested_user_id, include_admin=True)
        updated = False
        if profile is not None:
            updated_profile = _persist_local_profile(
                store,
                profile_name=str(profile.get("profile_name") or ""),
                username=str(profile.get("username") or ""),
                password_hash=_normalize_local_password_hash(
                    _request_payload_value(request, submitted, "password"),
                    fallback=str(profile.get("password_hash") or ""),
                ),
                token=str(profile.get("token") or ""),
                login_content=_json_deep_copy(profile.get("login_content") or {}),
                fresh_auth=_json_deep_copy(profile.get("fresh_auth") or {}),
                vuex_state=_json_deep_copy(profile.get("vuex_state") or {}),
            )
            updated = bool(updated_profile)
        return _local_json_record(_success_payload({"is_update": updated}))

    if normalized_path == "/java-api/school/tch/employeeSetting/resetWeMiniOpenid":
        submitted = _load_request_payload(request_body)
        requested_user_id = _parse_int_like(_request_payload_value(request, submitted, "userId", "id"))
        profile = _find_staff_profile(store, user_id=requested_user_id, include_admin=True)
        deleted = False
        if profile is not None:
            fresh_auth = _json_deep_copy(profile.get("fresh_auth") or {})
            user_info = fresh_auth.get("userInfo") if isinstance(fresh_auth.get("userInfo"), dict) else {}
            user_info["weMiniOpenid"] = None
            user_info["openId"] = None
            user_info["authorizerOpenid"] = None
            user_info["parentWeChat"] = ""
            user_info["wcmFlag"] = ""
            fresh_auth["userInfo"] = user_info
            vuex_state = _json_deep_copy(profile.get("vuex_state") or {})
            user_state = vuex_state.get("user") if isinstance(vuex_state.get("user"), dict) else {}
            if isinstance(user_state.get("userInfo"), dict):
                user_state["userInfo"].update(
                    {
                        "weMiniOpenid": None,
                        "openId": None,
                        "authorizerOpenid": None,
                        "parentWeChat": "",
                        "wcmFlag": "",
                    }
                )
                vuex_state["user"] = user_state
            updated_profile = _persist_local_profile(
                store,
                profile_name=str(profile.get("profile_name") or ""),
                username=str(profile.get("username") or ""),
                password_hash=str(profile.get("password_hash") or ""),
                token=str(profile.get("token") or ""),
                login_content=_json_deep_copy(profile.get("login_content") or {}),
                fresh_auth=fresh_auth,
                vuex_state=vuex_state,
            )
            deleted = bool(updated_profile)
        return _local_json_record(_success_payload({"is_delete": deleted}))

    if path == "/api/get/homepage":
        return _local_json_record(_success_payload(_build_homepage_content(store, request)))
    if path == "/api/admin/get/subject/list":
        # Course-management (course-subject) page expects a paged subject list.
        return _local_json_record(_success_payload({
            "subjectList": [],
            "list": [],
            "rows": [],
            "total": 0,
            "page_no": 1,
            "page_size": 20,
        }))

    if path == "/api/get/video/type/list":
        # Course-list page (backoffice) expects the catalog of video types.
        return _local_json_record(_success_payload({
            "videoTypeList": [],
            "list": [],
            "rows": [],
        }))

    if path == "/api/admin/get/video/list":
        # /background/courselist expects a paged video list (admin catalog).
        return _local_json_record(_success_payload({
            "videoList": [],
            "list": [],
            "rows": [],
            "total": 0,
            "page_no": 1,
            "page_size": 20,
        }))

    if path == "/api/admin/get/role/list":
        # /background/courselist page expects the role catalog.
        return _local_json_record(_success_payload({
            "roleList": [],
            "list": [],
            "rows": [],
        }))

    if path == "/api/admin/get/run/training/list":
        # Course training admin page expects a paged training run list.
        return _local_json_record(_success_payload({
            "trainingList": [],
            "list": [],
            "rows": [],
            "total": 0,
            "page_no": 1,
            "page_size": 20,
        }))

    if path == "/api/prepare/get/currculumMaterialList":
        # Curriculum-detail page sometimes calls this without a curriculum_id
        # (e.g. on first load before a course is selected). The captured
        # responses only cover the parameterized variant, so return a benign
        # empty list to keep the page quiet. We also include a placeholder
        # ``curriculumInfo`` object so that Vue templates which read fields
        # like ``curriculumInfo.img_url`` (chunk-5b483ec6 / curriculum-detail)
        # can still render without ``Cannot read properties of undefined``.
        return _local_json_record(_success_payload({
            "curriculumInfo": {},
            "curriculumMaterialList": [],
            "currculumMaterialList": [],
            "list": [],
            "rows": [],
            "total": 0,
            "page_no": 1,
            "page_size": 200,
        }))


    if path == "/java-api/school/edu/campus/queryListByUserId":
        resolved_profile = _resolve_profile(store, request)
        profile_name = resolved_profile["profile_name"] if resolved_profile else "teacher"
        rows = _build_user_campus_rows(store, profile_name)
        return _local_json_record(_success_payload(rows))

    if path == "/api/get/campus/subject/list":
        subjects = _teacher_subject_catalog(store)
        return _local_json_record(_success_payload({"campusSubjectList": subjects}))

    if path == "/api/getSubject":
        subjects = _teacher_subject_catalog(store)
        return _local_json_record(
            _success_payload(
                {
                    "subjectList": subjects,
                    "campusSubjectList": subjects,
                    "list": subjects,
                    "rows": subjects,
                }
            )
        )

    if path == "/api/get/school/subject/list":
        subjects = _teacher_subject_catalog(store)
        return _local_json_record(_success_payload({"subjectList": subjects}))

    if path == "/api/get/zone/school/subject/list":
        subjects = _teacher_subject_catalog(store)
        return _local_json_record(_success_payload({"subjectList": subjects}))

    if path == "/api/getSubjectAndCurriculumListForClassAddLesson":
        subjects = _teacher_subject_catalog(store)
        context_class_id = _resolve_class_context_id(request)
        if context_class_id is not None:
            context_class_row = store.find_class(context_class_id) or {}
            context_subject_ids = {
                subject_id
                for subject_id in (
                    _coerce_int(value)
                    for value in (
                        context_class_row.get("subjectIdList") or context_class_row.get("subject_id_list") or []
                    )
                )
                if subject_id is not None
            }
            if context_subject_ids:
                subjects = [
                    subject
                    for subject in subjects
                    if _coerce_int((subject or {}).get("id")) in context_subject_ids
                ]
        curriculum_rows = _build_teacher_curriculum_rows(store, request)
        return _local_json_record(
            _success_payload(
                {
                    "subjectList": subjects,
                    "curriculumList": curriculum_rows,
                    "campusCurriculumList": curriculum_rows,
                    "list": curriculum_rows,
                    "rows": curriculum_rows,
                }
            )
        )

    if path == "/api/get/all/campus/all/curriculum/title/list":
        return _local_json_record(
            _success_payload(
                {
                    "campusCurriculumList": _build_curriculum_title_rows(store),
                }
            )
        )

    if path == "/api/get/campus/curriculum/list/by/page":
        rows = _build_campus_curriculum_auth_rows(store, request)
        page_no, page_size, start = _page_window(request)
        page_rows = rows[start:start + page_size]
        return _local_json_record(
            _success_payload(
                {
                    "campusAuthList": page_rows,
                    "total": len(rows),
                    "page_no": page_no,
                    "page_size": page_size,
                }
            )
        )

    if path == "/api/get/curriculum/list":
        rows = _build_admin_curriculum_rows(store, request)
        page_no, page_size, start = _page_window(request)
        page_rows = rows[start:start + page_size]
        return _local_json_record(
            _success_payload(
                {
                    "curriculum_list": page_rows,
                    "curriculumList": page_rows,
                    "total": len(rows),
                    "page_no": page_no,
                    "page_size": page_size,
                }
            )
        )

    if path == "/api/get/curriculum":
        return _local_json_record(_success_payload(_build_admin_curriculum_detail_content(store, request)))

    if path == "/api/get/school/file/list":
        page_no, page_size, _ = _page_window(request)
        return _local_json_record(
            _success_payload(
                {
                    "fileList": [],
                    "schoolFileList": [],
                    "list": [],
                    "rows": [],
                    "total": 0,
                    "page_no": page_no,
                    "page_size": page_size,
                }
            )
        )

    if path == "/api/update/teaching/plan/zone/auth":
        submitted = _load_request_payload(request_body)
        teaching_plan_ids = _extract_teaching_plan_ids(submitted, request)
        zone_auth = _request_payload_value(request, submitted, "zone_auth", "zoneAuth")
        if teaching_plan_ids:
            store.bulk_upsert_teaching_plan_overlay(
                teaching_plan_ids,
                {"zone_auth": zone_auth},
            )
        return _local_json_record(_success_payload({"is_update": True, "updatedTchPlanIds": teaching_plan_ids}))

    if path == "/api/update/teaching/plan/oj/analysis/auth":
        submitted = _load_request_payload(request_body)
        teaching_plan_ids = _extract_teaching_plan_ids(submitted, request)
        oj_analysis_auth = _request_payload_value(request, submitted, "oj_analysis_auth", "ojAnalysisAuth")
        if teaching_plan_ids:
            store.bulk_upsert_teaching_plan_overlay(
                teaching_plan_ids,
                {"oj_analysis_auth": oj_analysis_auth},
            )
        return _local_json_record(_success_payload({"is_update": True, "updatedTchPlanIds": teaching_plan_ids}))

    if path == "/api/updateTeachingPlanTestCaseAuth":
        submitted = _load_request_payload(request_body)
        teaching_plan_ids = _extract_teaching_plan_ids(submitted, request)
        test_case_auth = _request_payload_value(request, submitted, "test_case_auth", "testCaseAuth", "oj_analysis_TEST")
        if teaching_plan_ids:
            store.bulk_upsert_teaching_plan_overlay(
                teaching_plan_ids,
                {"test_case_auth": test_case_auth},
            )
        return _local_json_record(_success_payload({"is_update": True, "updatedTchPlanIds": teaching_plan_ids}))

    if path == "/api/updateTeachingPlanEditorShowhintAuth":
        submitted = _load_request_payload(request_body)
        teaching_plan_ids = _extract_teaching_plan_ids(submitted, request)
        editor_showhint_auth = _request_payload_value(request, submitted, "editor_showhint_auth", "editorShowhintAuth")
        if teaching_plan_ids:
            store.bulk_upsert_teaching_plan_overlay(
                teaching_plan_ids,
                {"editor_showhint_auth": editor_showhint_auth},
            )
        return _local_json_record(_success_payload({"is_update": True, "updatedTchPlanIds": teaching_plan_ids}))

    if path == "/api/tch/get/tch/curriculum":
        rows = _build_teacher_curriculum_rows(store, request)
        page_no, page_size, start = _page_window(request)
        page_rows = rows[start:start + page_size]
        return _local_json_record(
            _success_payload(
                {
                    "curriculumList": page_rows,
                    "curriculum_list": page_rows,
                    "total": len(rows),
                    "page_no": page_no,
                    "page_size": page_size,
                }
            )
        )

    if path == "/api/getTchPlanListForAddTmp":
        submitted = _load_request_payload(request_body)
        rows = _build_teacher_teaching_plan_rows(store, request)
        current_tch_plan_id = _parse_int_like(_request_payload_value(request, submitted, "tchPlanId"))
        class_name = str(_request_payload_value(request, submitted, "className") or "").strip().lower()
        sign_state = str(_request_payload_value(request, submitted, "sign_state") or "").strip()
        start_date = str(_request_payload_value(request, submitted, "start_date") or "").strip()
        end_date = str(_request_payload_value(request, submitted, "end_date") or "").strip()

        filtered_rows: list[dict[str, Any]] = []
        for row in rows:
            row_id = _coerce_int(row.get("id"))
            if current_tch_plan_id is not None and row_id == current_tch_plan_id:
                continue
            if class_name:
                candidate_class_name = str(row.get("className") or row.get("class_name") or "").strip().lower()
                if class_name not in candidate_class_name:
                    continue
            if sign_state:
                candidate_sign_state = str(row.get("signState") or row.get("sign_state") or "").strip()
                if candidate_sign_state != sign_state:
                    continue
            if start_date:
                candidate_start_date = str(row.get("start_class_date") or row.get("class_date") or "").strip()
                if candidate_start_date and candidate_start_date < start_date:
                    continue
            if end_date:
                candidate_end_date = str(row.get("end_class_date") or row.get("class_date") or "").strip()
                if candidate_end_date and candidate_end_date > end_date:
                    continue
            filtered_rows.append(row)

        page_no, page_size, start = _page_window(request)
        page_rows = filtered_rows[start:start + page_size]
        return _local_json_record(
            _success_payload(
                {
                    "teachingPlan": page_rows,
                    "teachingPlanList": page_rows,
                    "list": page_rows,
                    "rows": page_rows,
                    "total": len(filtered_rows),
                    "page_no": page_no,
                    "page_size": page_size,
                }
            )
        )

    if path in {"/api/tch/get/teaching/plan/list", "/api/get/teaching/plan/list"}:
        rows = _build_teacher_teaching_plan_rows(store, request)
        class_id = _extract_class_id_from_request(request)
        if class_id is not None:
            rows = [
                {
                    **_json_deep_copy(row),
                    "originalIndex": index,
                }
                for index, row in enumerate(rows)
                if isinstance(row, dict) and _coerce_int(row.get("curriculum_class_id")) == class_id
            ]
            class_info_seed = {}
            for row in rows:
                candidate = row.get("classInfo")
                if isinstance(candidate, dict):
                    class_info_seed = candidate
                    break
            class_info = _build_class_info_for_detail_page(store, class_id, class_info_seed)
            return _local_json_record(
                _success_payload(
                    {
                        "teaching_plan_list": rows,
                        "teachingPlan": rows,
                        "teachingPlanList": rows,
                        "list": rows,
                        "rows": rows,
                        "classInfo": class_info,
                        "total": len(rows),
                        "page_no": 1,
                        "page_size": len(rows) or 1,
                    }
                )
            )
        page_no, page_size, start = _page_window(request)
        page_rows = rows[start:start + page_size]
        return _local_json_record(
            _success_payload(
                {
                    "teachingPlan": page_rows,
                    "teachingPlanList": page_rows,
                    "list": page_rows,
                    "rows": page_rows,
                    "total": len(rows),
                    "page_no": page_no,
                    "page_size": page_size,
                }
            )
        )

    if path == "/api/tch/getTchPlanListForEvaluate":
        rows = _build_teacher_teaching_plan_rows(store, request)
        page_no, page_size, start = _page_window(request)
        page_rows = rows[start:start + page_size]
        return _local_json_record(
            _success_payload(
                {
                    "tchPlanList": page_rows,
                    "teachingPlanList": page_rows,
                    "list": page_rows,
                    "rows": page_rows,
                    "total": len(rows),
                    "page_no": page_no,
                    "page_size": page_size,
                }
            )
        )

    if path == "/api/tch/get/stu/tch/plan/list/by/tch/id":
        return _local_json_record(_success_payload(_build_teacher_classroom_student_plan_rows(store, request)))

    if path == "/api/tch/getStuTchPlanListForEvaluate":
        rows = _build_teacher_evaluate_student_rows(store, request)
        page_no, page_size, start = _page_window(request)
        page_rows = rows[start:start + page_size]
        return _local_json_record(
            _success_payload(
                {
                    "stuTchPlanList": page_rows,
                    "list": page_rows,
                    "rows": page_rows,
                    "total": len(rows),
                    "page_no": page_no,
                    "page_size": page_size,
                }
            )
        )

    if path == "/api/tch/class/get/classlist":
        resolved_profile = _resolve_profile(store, request)
        profile_name = resolved_profile["profile_name"] if resolved_profile else _resolve_profile_name(store, request)
        profile_role = _profile_role(profile_name, resolved_profile)
        if profile_role == "student":
            rows, user_subject = _build_student_class_rows(store, request)
        else:
            rows, user_subject = _build_teacher_class_rows(store, request)
        page_no, page_size, start = _page_window(request, default_page_size=16)
        page_rows = rows[start:start + page_size]
        return _local_json_record(
            _success_payload(
                {
                    "userSubject": user_subject,
                    "classlist": page_rows,
                    "classList": page_rows,
                    "classlist_total": len(rows),
                    "page_no": page_no,
                    "page_size": page_size,
                }
            )
        )

    if path == "/api/create/class":
        submitted = _load_request_payload(request_body)
        payload = dict(submitted) if isinstance(submitted, dict) else {}
        resolved_profile = _resolve_profile(store, request)
        profile_name = resolved_profile["profile_name"] if resolved_profile else "teacher"
        teacher_user_info = _hydrate_teacher_user_info(store, _teacher_user_info(store, profile_name), profile_name)
        if payload.get("campusId") in (None, "") and payload.get("educational_institution_campus_id") in (None, ""):
            payload["campusId"] = _teacher_primary_campus_id(store, profile_name) or 0
        if payload.get("lecturer_id") in (None, ""):
            payload["lecturer_id"] = _coerce_int(teacher_user_info.get("id") or teacher_user_info.get("userId")) or 0
        if payload.get("lecturer_name") in (None, ""):
            payload["lecturer_name"] = (
                teacher_user_info.get("realName")
                or teacher_user_info.get("realname")
                or teacher_user_info.get("userRealname")
                or ""
            )
        created_class = store.upsert_local_class(payload) or {}
        return _local_json_record(
            _success_payload(
                {
                    "id": created_class.get("id") or 0,
                    "classId": created_class.get("id") or 0,
                    "classInfo": created_class,
                }
            )
        )

    if path == "/api/update/classes":
        submitted = _load_request_payload(request_body)
        payload = dict(submitted) if isinstance(submitted, dict) else {}
        updated_class = store.upsert_local_class(payload) or {}
        return _local_json_record(
            _success_payload(
                {
                    "is_update": bool(updated_class),
                    "id": updated_class.get("id") or 0,
                    "classId": updated_class.get("id") or 0,
                    "classInfo": updated_class,
                }
            )
        )

    if path == "/api/updateClassWeekJson":
        submitted = _load_request_payload(request_body)
        payload = dict(submitted) if isinstance(submitted, dict) else {}
        updated_class = store.upsert_local_class(payload) or {}
        return _local_json_record(
            _success_payload(
                {
                    "is_update": bool(updated_class),
                    "id": updated_class.get("id") or 0,
                    "classId": updated_class.get("id") or 0,
                    "classInfo": updated_class,
                }
            )
        )

    if path == "/api/update/classes/end/class/state":
        submitted = _load_request_payload(request_body)
        payload = dict(submitted) if isinstance(submitted, dict) else {}
        class_id = _resolve_class_context_id(request, submitted)
        requested_end_class_state = _parse_int_like(
            _request_payload_value(request, submitted, "end_class_state", "endClassState", "state")
        )
        if class_id is not None:
            payload["id"] = class_id
            payload["end_class_state"] = 1 if requested_end_class_state is None else requested_end_class_state
            updated_class = store.upsert_local_class(payload) or {}
        else:
            updated_class = {}
        updated_class_id = _coerce_int(updated_class.get("id")) if updated_class else None
        updated_class_ids = [updated_class_id] if updated_class_id is not None else []
        return _local_json_record(
            _success_payload(
                {
                    "is_update": bool(updated_class),
                    "updatedClassIds": updated_class_ids,
                    "successCount": len(updated_class_ids),
                    "id": updated_class_id or 0,
                    "classId": updated_class_id or 0,
                    "classInfo": updated_class,
                }
            )
        )

    if path == "/api/get/classes/list":
        return _local_json_record(_success_payload(_build_classes_list_content(store, request)))

    if path == "/api/add/student/class/relation":
        submitted = _load_request_payload(request_body)
        class_id = _extract_class_id_from_request(request, submitted)
        student_ids = _extract_student_ids(submitted, request)
        if class_id is not None:
            store.ensure_local_class_membership_snapshot(class_id)
            for student_id in student_ids:
                store.upsert_local_class_student_relation(
                    class_id=class_id,
                    student_user_id=student_id,
                    in_class_date=datetime.now().strftime("%Y-%m-%d"),
                )
        return _local_json_record(
            _success_payload(
                {
                    "is_update": True,
                    "is_create": True,
                    "failarr": [],
                    "failArr": [],
                    "classId": class_id or 0,
                    "updatedStuIds": student_ids,
                    "successCount": len(student_ids),
                }
            )
        )

    if path == "/api/del/student/class/relation":
        submitted = _load_request_payload(request_body)
        class_id = _extract_class_id_from_request(request, submitted)
        student_ids = _extract_student_ids(submitted, request)
        deleted_student_ids: list[int] = []
        if class_id is not None:
            store.ensure_local_class_membership_snapshot(class_id)
            deleted_student_ids = store.delete_local_class_student_relations(class_id, student_ids)
        return _local_json_record(
            _success_payload(
                {
                    "is_delete": True,
                    "failArr": [],
                    "failarr": [],
                    "classId": class_id or 0,
                    "updatedStuIds": deleted_student_ids,
                    "successCount": len(deleted_student_ids),
                }
            )
        )

    if path == "/api/change/stu/class":
        submitted = _load_request_payload(request_body)
        student_ids = _extract_student_ids(submitted, request)
        source_class_id = _parse_int_like(
            _request_payload_value(
                request,
                submitted,
                "oldClassId",
                "sourceClassId",
                "fromClassId",
                "currentClassId",
                "now_class_id",
                "nowClassId",
            )
        )
        target_class_id = _parse_int_like(
            _request_payload_value(
                request,
                submitted,
                "classId",
                "newClassId",
                "targetClassId",
                "curriculumClassId",
                "change_class_id",
                "changeClassId",
            )
        )
        if source_class_id is not None:
            store.ensure_local_class_membership_snapshot(source_class_id)
            store.delete_local_class_student_relations(source_class_id, student_ids)
        if target_class_id is not None:
            store.ensure_local_class_membership_snapshot(target_class_id)
            for student_id in student_ids:
                store.upsert_local_class_student_relation(
                    class_id=target_class_id,
                    student_user_id=student_id,
                    in_class_date=datetime.now().strftime("%Y-%m-%d"),
                )
        return _local_json_record(
            _success_payload(
                {
                    "is_update": True,
                    "is_change": bool(student_ids and target_class_id is not None),
                    "sourceClassId": source_class_id or 0,
                    "targetClassId": target_class_id or 0,
                    "updatedStuIds": student_ids,
                    "successCount": len(student_ids),
                }
            )
        )

    if path == "/api/get/class/list/for/stu/change/class":
        content = _build_classes_list_content(store, request)
        rows = content.get("class_list") if isinstance(content, dict) else []
        return _local_json_record(
            _success_payload(
                {
                    "classList": rows,
                    "class_list": rows,
                    "list": rows,
                    "rows": rows,
                    "total": content.get("total") if isinstance(content, dict) else len(rows),
                    "page_no": content.get("page_no") if isinstance(content, dict) else 1,
                    "page_size": content.get("page_size") if isinstance(content, dict) else len(rows) or 1,
                }
            )
        )

    if path == "/api/get/class/student/list":
        content = _build_class_student_list_content(store, request)
        rows = content.get("studentList") if isinstance(content, dict) else []
        flattened_rows = [
            _flatten_class_student_detail_row(row)
            for row in rows
            if isinstance(row, dict)
        ]
        if isinstance(content, dict):
            content = {
                **content,
                "content": flattened_rows,
                "records": flattened_rows,
                "totalSize": content.get("total") if content.get("total") is not None else len(flattened_rows),
            }
        return _local_json_record(_success_payload(content))

    if path in {"/api/getNoXmStuForClassAddStu", "/api/xmedu/getStuListForAddStuToClass"}:
        submitted = _load_request_payload(request_body)
        class_id = _extract_class_id_from_request(request, submitted)
        rows = _build_student_candidate_rows_for_class(
            store,
            request,
            class_id=class_id,
            include_existing=False,
            include_xm_goods=True,
        )
        page_no, page_size, start = _page_window(request)
        page_rows = rows[start:start + page_size]
        return _local_json_record(
            _success_payload(
                {
                    "studentList": page_rows,
                    "stuList": page_rows,
                    "list": page_rows,
                    "rows": page_rows,
                    "total": len(rows),
                    "page_no": page_no,
                    "page_size": page_size,
                }
            )
        )

    if path == "/api/get/no/divide/student/list":
        submitted = _load_request_payload(request_body)
        class_id = _extract_class_id_from_request(request, submitted)
        rows = _build_no_divide_student_candidate_rows_for_class(
            store,
            request,
            class_id=class_id,
        )
        page_no, page_size, start = _page_window(request)
        page_rows = rows[start:start + page_size]
        return _local_json_record(
            _success_payload(
                {
                    "studentList": page_rows,
                    "stuList": page_rows,
                    "list": page_rows,
                    "rows": page_rows,
                    "total": len(rows),
                    "page_no": page_no,
                    "page_size": page_size,
                }
            )
        )

    if path == "/api/get/receipt/charge/goods/list":
        submitted = _load_request_payload(request_body)
        receipt_id = _parse_int_like(_request_payload_value(request, submitted, "receipt_id", "receiptId", "id"))
        rows = _build_local_receipt_charge_goods_rows(store, receipt_id)
        return _local_json_record(
            _success_payload(
                {
                    "receiptChargeGoodsList": rows,
                    "receiptGoodsList": rows,
                    "chargeGoodsList": rows,
                    "goodsList": rows,
                    "list": rows,
                    "rows": rows,
                    "total": len(rows),
                }
            )
        )

    if path == "/api/get/receipt/account/list":
        submitted = _load_request_payload(request_body)
        receipt_id = _parse_int_like(_request_payload_value(request, submitted, "receipt_id", "receiptId", "id"))
        rows = _build_local_receipt_account_rows(store, receipt_id)
        return _local_json_record(
            _success_payload(
                {
                    "receiptAccountList": rows,
                    "accountList": rows,
                    "list": rows,
                    "rows": rows,
                    "total": len(rows),
                }
            )
        )

    if path == "/api/add/stu/to/teaching/plan":
        submitted = _load_request_payload(request_body)
        teaching_plan_id = _parse_int_like(_request_payload_value(request, submitted, "tchPlanId", "teachingPlanId", "id"))
        student_ids = _extract_student_ids(submitted, request)
        if teaching_plan_id is not None:
            plan = _find_teaching_plan(store, teaching_plan_id) or {}
            plan_cost_lesson_hour = plan.get("cost_lesson_hour")
            for student_id in student_ids:
                store.upsert_local_teaching_plan_student_relation(
                    teaching_plan_id=teaching_plan_id,
                    student_user_id=student_id,
                    cost_lesson_hour=plan_cost_lesson_hour,
                )
        return _local_json_record(
            _success_payload(
                {
                    "is_update": True,
                    "tchPlanId": teaching_plan_id or 0,
                    "updatedStuIds": student_ids,
                    "successCount": len(student_ids),
                }
            )
        )

    if path in {"/api/get/formal/student/list/for/addto/tch/plan", "/api/xmedu/getStuListForAddStuToTchPlan"}:
        submitted = _load_request_payload(request_body)
        teaching_plan_id = _parse_int_like(_request_payload_value(request, submitted, "tchPlanId", "teachingPlanId", "id"))
        rows = _build_student_candidate_rows_for_teaching_plan(
            store,
            request,
            teaching_plan_id=teaching_plan_id,
            include_xm_goods=True,
        )
        page_no, page_size, start = _page_window(request)
        page_rows = rows[start:start + page_size]
        return _local_json_record(
            _success_payload(
                {
                    "studentList": page_rows,
                    "stuList": page_rows,
                    "list": page_rows,
                    "rows": page_rows,
                    "total": len(rows),
                    "page_no": page_no,
                    "page_size": page_size,
                }
            )
        )

    if path == "/api/get/teaching/plan/by/class/id":
        return _local_json_record(_success_payload(_build_teaching_plan_by_class_content(store, request)))

    if path == "/api/getLessonListForClassAddLesson":
        submitted = _load_request_payload(request_body)
        class_id = _resolve_class_context_id(request, submitted)
        rows = _build_lesson_candidate_rows_for_class(store, request, class_id=class_id)
        page_no, page_size, start = _page_window(request)
        page_rows = rows[start:start + page_size]
        return _local_json_record(
            _success_payload(
                {
                    "lessonList": page_rows,
                    "curriculumMaterialList": page_rows,
                    "list": page_rows,
                    "rows": page_rows,
                    "total": len(rows),
                    "page_no": page_no,
                    "page_size": page_size,
                }
            )
        )

    if path == "/api/update/teaching/plan":
        submitted = _load_request_payload(request_body)
        payload = dict(submitted) if isinstance(submitted, dict) else {}
        updated_plan = store.upsert_local_teaching_plan(payload) or {}
        return _local_json_record(
            _success_payload(
                {
                    "is_update": bool(updated_plan),
                    "tchPlanId": updated_plan.get("id") or 0,
                    "teachingPlanId": updated_plan.get("id") or 0,
                    "tchPlanInfo": updated_plan,
                }
            )
        )

    if path == "/api/delete/tch/plan":
        submitted = _load_request_payload(request_body)
        teaching_plan_ids = _extract_teaching_plan_ids(submitted, request)
        deleted_ids: list[int] = []
        for teaching_plan_id in teaching_plan_ids:
            deleted_plan = store.mark_teaching_plan_deleted(teaching_plan_id)
            if deleted_plan is not None:
                deleted_ids.append(teaching_plan_id)
        return _local_json_record(
            _success_payload(
                {
                    "is_delete": True,
                    "updatedTchPlanIds": deleted_ids,
                    "successCount": len(deleted_ids),
                }
            )
        )

    if path == "/api/bulk/add/tch/plan/to/class":
        submitted = _load_request_payload(request_body)
        class_id = _extract_class_id_from_request(request, submitted)
        lesson_ids = _extract_lesson_ids(submitted, request)
        created_plan_ids: list[int] = []
        if class_id is not None:
            class_row = store.find_class(class_id) or {}
            existing_plans = _plan_rows_for_class(store, class_id)
            next_sort_num = max((_coerce_int(plan.get("sort_num")) or 0 for plan in existing_plans), default=0) + 1
            for lesson_index, lesson_id in enumerate(lesson_ids):
                material = store.find_curriculum_material(lesson_id) or {}
                class_date, start_class_date, end_class_date = _next_class_schedule_strings(class_row, existing_plans, lesson_index)
                created_plan = store.upsert_local_teaching_plan(
                    {
                        "curriculum_class_id": class_id,
                        "educational_institution_campus_id": (
                            class_row.get("educational_institution_campus_id")
                            or _teacher_primary_campus_id(store)
                            or 0
                        ),
                        "lecturer_id": class_row.get("lecturer_id"),
                        "lecturer_name": class_row.get("lecturer_name"),
                        "subject_id": material.get("subject_id")
                        or next(
                            (
                                _coerce_int(value)
                                for value in (class_row.get("subjectIdList") or class_row.get("subject_id_list") or [])
                                if _coerce_int(value) is not None
                            ),
                            0,
                        ),
                        "curriculum_id": material.get("curriculum_id")
                        or next(
                            (
                                _coerce_int(value)
                                for value in (class_row.get("curriculumIdList") or class_row.get("curriculum_id_list") or [])
                                if _coerce_int(value) is not None
                            ),
                            0,
                        ),
                        "curriculum_meterial_id": lesson_id,
                        "title": material.get("title") or f"Lesson {lesson_id}",
                        "custom_lesson_title": material.get("title") or f"Lesson {lesson_id}",
                        "class_date": class_date,
                        "start_class_date": start_class_date,
                        "end_class_date": end_class_date,
                        "sign_state": 0,
                        "sign_state_new": 0,
                        "sort_num": next_sort_num + lesson_index,
                    }
                )
                if created_plan is None:
                    continue
                created_plan_ids.append(_coerce_int(created_plan.get("id")) or 0)
                created_plan_view = store.find_teaching_plan(created_plan.get("id")) or created_plan
                existing_plans.append(created_plan_view)
        return _local_json_record(
            _success_payload(
                {
                    "is_update": True,
                    "classId": class_id or 0,
                    "tchPlanIds": created_plan_ids,
                    "successCount": len(created_plan_ids),
                }
            )
        )

    if path == "/java-api/school/intend/board/soa":
        metrics = _build_dashboard_metric_snapshot(store, request, request_body)
        return _local_json_record(
            _success_payload(
                {
                    "intendNum": metrics["intendNum"],
                    "todayIntendNum": metrics["todayIntendNum"],
                    "todayComeNum": metrics["todayComeNum"],
                }
            )
        )

    if path == "/java-api/school/stu/board/recSoa":
        metrics = _build_dashboard_metric_snapshot(store, request, request_body)
        return _local_json_record(
            _success_payload(
                {
                    "formalNum": metrics["formalNum"],
                    "todayFormalNum": metrics["todayFormalNum"],
                    "tryNum": metrics["tryNum"],
                    "todayTryNum": metrics["todayTryNum"],
                }
            )
        )

    if path == "/java-api/school/tch/board/recordSoa":
        metrics = _build_dashboard_metric_snapshot(store, request, request_body)
        return _local_json_record(
            _success_payload(
                {
                    "lessonRecordNum": metrics["lessonRecordNum"],
                    "todayLessonRecordNum": metrics["todayLessonRecordNum"],
                }
            )
        )

    if path == "/java-api/school/stu/board/incomeSoa":
        metrics = _build_dashboard_metric_snapshot(store, request, request_body)
        return _local_json_record(
            _success_payload(
                {
                    "inCome": metrics["inCome"],
                    "todayInCome": metrics["todayInCome"],
                    "consumeHour": metrics["consumeHour"],
                    "todayConsumeHour": metrics["todayConsumeHour"],
                }
            )
        )

    if path == "/java-api/school/intend/board/echarts/stat":
        return _local_json_record(_success_payload(_build_dashboard_clue_chart_content(store, request, request_body)))

    if path == "/java-api/school/stu/board/echarts/recStat":
        return _local_json_record(_success_payload(_build_dashboard_student_pie_content(store, request, request_body)))

    if path == "/java-api/school/tch/board/echarts/recordStat":
        return _local_json_record(_success_payload(_build_dashboard_teacher_record_chart_content(store, request, request_body)))

    if path == "/java-api/school/stu/board/echarts/consumeStat":
        return _local_json_record(_success_payload(_build_dashboard_student_consume_chart_content(store, request, request_body)))

    if path == "/java-api/school/tch/board/echarts/attnStat":
        return _local_json_record(_success_payload(_build_dashboard_teacher_attendance_content(store, request, request_body)))

    if path == "/java-api/school/edu/campus/echarts/attnStat":
        return _local_json_record(_success_payload(_build_dashboard_campus_attendance_content(store, request, request_body)))

    if path == "/java-api/school/edu/campus/consumeDayStat":
        return _local_json_record(_success_payload(_build_dashboard_campus_consume_content(store, request, request_body)))

    if path == "/java-api/school/tch/board/classCmtQuery":
        return _local_json_record(_success_payload(_build_dashboard_class_comment_content(store, request, request_body)))

    if path == "/java-api/school/tch/selectTchListByCampus":
        return _local_json_record(_success_payload(_build_dashboard_teacher_rows(store, request, request_body)))

    if path == "/api/get/educational_institution_info":
        return _local_json_record(_success_payload(_build_educational_institution_info_content(store)))

    if path == "/api/get/school/board/main/data":
        return _local_json_record(_success_payload(_build_board_main_data_content(store, request)))

    if path == "/api/get/tch/notice/list/for/school/board":
        return _local_json_record(_success_payload(_build_school_notice_board_content(store, request)))

    if path == "/java-api/school/visitRecord/selectList":
        return _local_json_record(_success_payload(_build_visit_record_content(store, request, request_body)))

    if path == "/api/getTchRecentNotReadNotice":
        return _local_json_record(_success_payload(_build_recent_notice_content(store)))

    if path == "/api/getTeachingPlanStuListWithXmArr":
        return _local_json_record(_success_payload(_build_teaching_plan_student_rows(store, request)))

    if path == "/api/stu/get/indexinfo/for/new":
        return _local_json_record(_success_payload(_build_student_index_info_content(store, request)))

    if path == "/api/stu/get/index/tch/work/list":
        dataset = _build_student_work_dataset(store, request)
        return _local_json_record(
            _success_payload(
                {
                    "workList": dataset["rows"],
                    "total": dataset["total"],
                    "page_no": dataset["page_no"],
                    "page_size": dataset["page_size"],
                    "pageNum": dataset["page_no"],
                    "pageSize": dataset["page_size"],
                }
            )
        )

    if path == "/api/stu/get/stu/subject/auth":
        subjects = _student_subject_rows(store)
        return _local_json_record(
            _success_payload(
                {
                    "subjectList": subjects,
                    "userSubject": subjects,
                    "stuSubjectList": subjects,
                    "list": subjects,
                    "rows": subjects,
                    "total": len(subjects),
                }
            )
        )

    if path == "/api/stu/get/stu/work/subject":
        subjects = _student_subject_rows(store)
        return _local_json_record(
            _success_payload(
                {
                    "subjectList": subjects,
                    "userSubject": subjects,
                    "list": subjects,
                    "rows": subjects,
                    "total": len(subjects),
                }
            )
        )

    if path == "/api/update/updateAllNoticeRead":
        return _local_json_record(_success_payload({"is_update": True}))

    if path == "/java-api/school/currCls/countSignedTchPlan":
        return _local_json_record(_success_payload(_build_signed_teaching_plan_count_content(store, request, request_body)))

    if path == "/api/stu/get/tch/work/list":
        dataset = _build_student_work_dataset(store, request)
        return _local_json_record(
            _success_payload(
                {
                    "workList": dataset["rows"],
                    "subjectList": dataset["subjectList"],
                    "total": dataset["total"],
                    "page_no": dataset["page_no"],
                    "page_size": dataset["page_size"],
                    "pageNum": dataset["page_no"],
                    "pageSize": dataset["page_size"],
                }
            )
        )

    if path == "/api/stu/get/stu/class/list":
        rows, user_subject = _build_student_class_rows(store, request)
        page_no, page_size, start = _page_window(request, default_page_size=16)
        page_rows = rows[start:start + page_size]
        return _local_json_record(
            _success_payload(
                {
                    "userSubject": user_subject,
                    "classlist": page_rows,
                    "classList": page_rows,
                    "list": page_rows,
                    "rows": page_rows,
                    "total": len(rows),
                    "classlist_total": len(rows),
                    "page_no": page_no,
                    "page_size": page_size,
                    "pageNum": page_no,
                    "pageSize": page_size,
                }
            )
        )

    if path in {
        "/api/stu/get/stu/tch/plan/list",
        "/api/stu/get/stu/timetable",
        "/api/stu/get/stu/timetable/new",
        "/api/stu/getStuTimetableNewWithOutPageInfo",
    }:
        return _local_json_record(_success_payload(_build_student_timetable_rows(store, request)))

    if path == "/api/get/tch/lesson/work":
        return _local_json_record(_success_payload({"tchLessonWork": None}))

    if path == "/api/get/tch/lesson/work/list":
        dataset = _build_local_work_dataset(store, request)
        return _local_json_record(
            _success_payload(
                {
                    "workList": dataset["rows"],
                    "lessonWorkList": dataset["rows"],
                    "tchLessonWorkList": dataset["rows"],
                    "total": dataset["total"],
                    "page_no": dataset["page_no"],
                    "page_size": dataset["page_size"],
                    "tchLessonWorkInfo": dataset["lesson_info"],
                    "tchLeesonWorkInfo": dataset["lesson_info"],
                }
            )
        )

    if path == "/api/tch/get/stu/lesson/tch/work/list":
        dataset = _build_local_work_dataset(
            store,
            request,
            requested_subject_code=_first_query_value(request, "subject_code") or _first_query_value(request, "subjectCode"),
            title_filter=_first_query_value(request, "title") or "",
        )
        return _local_json_record(
            _success_payload(
                {
                    "workList": dataset["rows"],
                    "total": dataset["total"],
                    "page_no": dataset["page_no"],
                    "page_size": dataset["page_size"],
                }
            )
        )

    if path == "/api/tch/get/tch/stu/tch/work/list":
        dataset = _build_local_work_dataset(
            store,
            request,
            requested_subject_code=_first_query_value(request, "subject_code") or _first_query_value(request, "subjectCode"),
            title_filter=_first_query_value(request, "title") or "",
        )
        return _local_json_record(
            _success_payload(
                {
                    **dataset["subject_snapshot"],
                    "lessonId": dataset["lesson_id"],
                    "lessonTitle": dataset["lesson_title"],
                    "workList": dataset["rows"],
                    "total": dataset["total"],
                    "page_no": dataset["page_no"],
                    "page_size": dataset["page_size"],
                }
            )
        )

    if path == "/api/getWorkListForCopyToStuTchPlan":
        submitted = _load_request_payload(request_body)
        return _local_json_record(_success_payload(_build_local_copy_work_content(store, request, submitted)))

    if path == "/api/tmpWorkCopyToStuTchPlan":
        submitted = _load_request_payload(request_body)
        work_id = _parse_int_like(_request_payload_value(request, submitted, "work_id"))
        tmp_work_id = _parse_int_like(_request_payload_value(request, submitted, "tmp_work_id"))
        is_update = work_id is not None and tmp_work_id is not None
        return _local_json_record(
            _success_payload(
                {
                    "is_update": is_update,
                    "workId": work_id or 0,
                    "tmpWorkId": tmp_work_id or 0,
                }
            )
        )

    if path == "/api/bulkUpdateTchPlanTemplate":
        submitted = _load_request_payload(request_body)
        source_tch_plan_id = _parse_int_like(_request_payload_value(request, submitted, "tchPlanId"))
        target_tch_plan_ids = _extract_teaching_plan_ids(submitted, request)
        if source_tch_plan_id is not None:
            target_tch_plan_ids = [target_id for target_id in target_tch_plan_ids if target_id != source_tch_plan_id]
        template_info = _teaching_plan_template_info(store, request, teaching_plan_id=source_tch_plan_id)
        if target_tch_plan_ids:
            store.bulk_upsert_teaching_plan_overlay(
                target_tch_plan_ids,
                {
                    "source_tch_plan_id": source_tch_plan_id,
                    "class_work_url": template_info.get("classWorkUrl"),
                    "example_work_url": template_info.get("exampleWorkUrl"),
                    "homework_work_url": template_info.get("homeworkWorkUrl"),
                },
            )
        return _local_json_record(
            _success_payload(
                {
                    "is_update": True,
                    "updatedTchPlanIds": target_tch_plan_ids,
                    "successCount": len(target_tch_plan_ids),
                }
            )
        )

    if path == "/api/bulkResetTchPlanTemplate":
        submitted = _load_request_payload(request_body)
        target_tch_plan_ids = _extract_teaching_plan_ids(submitted, request)
        for target_tch_plan_id in target_tch_plan_ids:
            store.upsert_teaching_plan_overlay(
                target_tch_plan_id,
                {
                    "class_work_url": None,
                    "example_work_url": None,
                    "homework_work_url": None,
                    "source_tch_plan_id": None,
                },
            )
        return _local_json_record(
            _success_payload(
                {
                    "is_update": True,
                    "updatedTchPlanIds": target_tch_plan_ids,
                    "successCount": len(target_tch_plan_ids),
                }
            )
        )

    if path == "/api/tch/xmedu/getSchoolOpenMissClass":
        rows, _ = _build_teacher_class_rows(store, request)
        return _local_json_record(
            _success_payload(
                {
                    "classList": rows,
                    "classlist": rows,
                    "list": rows,
                    "rows": rows,
                    "total": len(rows),
                }
            )
        )

    if path == "/api/tch/xmedu/getSchoolOpenMissClassOfTeachingPlan":
        rows = _build_teacher_teaching_plan_rows(store, request)
        return _local_json_record(
            _success_payload(
                {
                    "tchPlanList": rows,
                    "teachingPlanList": rows,
                    "classList": rows,
                    "list": rows,
                    "rows": rows,
                    "total": len(rows),
                }
            )
        )

    if path == "/api/test/school/question/bank/auth":
        return _local_json_record(_success_payload({"is_have_auth": True}))

    if path == "/api/get/school/banner/list":
        return _local_json_record(_success_payload({"bannerList": [], "banner_list": []}))

    if path == "/api/exam/get/school/exam/list":
        page_no, page_size, _ = _page_window(request)
        return _local_json_record(
            _success_payload(_empty_page_content(page_no, page_size, "examList", "schoolExamList", "list", "rows"))
        )

    if path == "/api/exam/getSchoolLessonExamList":
        page_no, page_size, _ = _page_window(request)
        return _local_json_record(
            _success_payload(
                _empty_page_content(
                    page_no,
                    page_size,
                    "examList",
                    "schoolLessonExamList",
                    "list",
                    "rows",
                )
            )
        )

    if path == "/api/exam/getKeepPaperList":
        page_no, page_size, _ = _page_window(request)
        return _local_json_record(
            _success_payload(
                _empty_page_content(page_no, page_size, "paperList", "keepPaperList", "list", "rows")
            )
        )

    if path == "/api/exam/getBankSourceInfo":
        source_id = _first_query_value(request, "source_id")
        return _local_json_record(_success_payload({"sourceInfo": _build_competition_source_info(store, source_id)}))

    if path == "/api/exam/getTestQuestionBankSourceTagListWithoutPage":
        return _local_json_record(_success_payload({"testQuestionBankSourceTagList": []}))

    if path == "/api/exam/get/school/question/bank/list":
        page_no, page_size, _ = _page_window(request)
        return _local_json_record(
            _success_payload(
                {
                    "questionBankList": [],
                    "question_bank_list": [],
                    "total": 0,
                    "page_no": page_no,
                    "page_size": page_size,
                }
            )
        )

    if path == "/api/admin/get/latest/sys/total/info":
        info = _build_admin_latest_total_info(store)
        return _local_json_record(_success_payload({"latestSysTotalInfo": info, **info}))

    if path == "/api/admin/get/school/num/by/school/subject":
        rows = _build_admin_subject_stat_rows(store)
        return _local_json_record(_success_payload({"schoolNumList": rows, "list": rows, "rows": rows}))

    if path == "/api/admin/get/stu/num/by/subject":
        rows = _build_admin_subject_stat_rows(store)
        return _local_json_record(_success_payload({"schoolNumList": rows, "list": rows, "rows": rows}))

    if path in {"/api/get/tch/training/list", "/api/admin/get/tch/training/list"}:
        page_no, page_size, _ = _page_window(request)
        return _local_json_record(
            _success_payload(_empty_page_content(page_no, page_size, "tchTrainingList", "list", "rows"))
        )

    if path in {"/api/get/tch/training/info", "/api/admin/get/tch/training/info"}:
        training_id = _coerce_int(_first_query_value(request, "tch_training_id")) or 0
        training_info = {
            "id": training_id,
            "tch_training_id": training_id,
            "title": "Local Training Placeholder",
            "post_state": 0,
            "chapterInfoArr": [
                {
                    "id": 0,
                    "tch_training_chapter_id": 0,
                    "title": "Local Chapter",
                    "sort_num": "01",
                    "videoInfoArr": [
                        {
                            "id": 0,
                            "tch_training_video_id": 0,
                            "title": "Local Video",
                            "video_url": "",
                        }
                    ],
                }
            ],
        }
        return _local_json_record(
            _success_payload(
                {
                    "tchTrainingInfo": training_info,
                    "runTrainingInfo": training_info,
                }
            )
        )

    if path == "/api/xm/getXmOrderList":
        page_no, page_size, _ = _page_window(request, default_page_size=10)
        return _local_json_record(
            _success_payload(
                {
                    "xmOrderListObj": [],
                    "finalAmountSum": 0,
                    "unpaidAmountSum": 0,
                    "total": 0,
                    "page_no": page_no,
                    "page_size": page_size,
                }
            )
        )

    if path == "/api/xm/getStuInfoForFinacialPages":
        student_id = _parse_int_like(_request_payload_value(request, None, "stuId", "studentId", "id", "student_user_id"))
        student_row = _candidate_student_row_by_id(store, student_id)
        if student_row is None:
            return _local_json_record(_success_payload({"stuBuyAmount": 0, "xmGoodsList": []}))
        goods_rows = _build_local_xm_goods_rows(student_row, store=store)
        return _local_json_record(
            _success_payload(
                {
                    "stuBuyAmount": 0,
                    "xmGoodsList": goods_rows,
                    "studentInfo": _json_deep_copy(student_row.get("studentUserInfo") or {}),
                    "stuInfo": _json_deep_copy(student_row.get("studentUserInfo") or {}),
                    "stuName": (student_row.get("studentUserInfo") or {}).get("realname") or student_row.get("name") or "",
                    "student_user_id": _coerce_int(student_row.get("id")) or 0,
                    "classList": _json_deep_copy(student_row.get("stuClassArr") or []),
                    "classStr": student_row.get("class_str") or "--",
                }
            )
        )

    if path == "/api/xm/getXmAccountInfoByStuId":
        student_id = _parse_int_like(_request_payload_value(request, None, "stuId", "studentId", "id", "student_user_id"))
        student_row = _candidate_student_row_by_id(store, student_id)
        account_rows = [_build_local_xm_account_row(store, student_row)] if student_row is not None else []
        return _local_json_record(
            _success_payload(
                {
                    "xmAccountList": account_rows,
                    "list": account_rows,
                    "rows": account_rows,
                }
            )
        )

    if path == "/api/getHeaderSet":
        table_type = (_first_query_value(request, "table_type") or "").strip()
        return _local_json_record(_success_payload({"headerList": _default_header_rows(table_type)}))

    if path == "/java-api/school/xmAccountStu/queryAccountList":
        submitted = _load_request_payload(request_body)
        page_num, page_size = _page_request_window(submitted)
        account_rows = [_build_local_xm_account_row(store, row) for row in _all_candidate_student_rows(store)]
        account_no_filter = str(_request_payload_value(request, submitted, "account_no", "accountNo") or "").strip().lower()
        student_name_filter = str(_request_payload_value(request, submitted, "stuNames", "stuName", "realname", "realName", "name") or "").strip().lower()
        filtered_rows: list[dict[str, Any]] = []
        for row in account_rows:
            if account_no_filter and account_no_filter not in str(row.get("account_no") or "").strip().lower():
                continue
            if student_name_filter and student_name_filter not in str(row.get("stuNames") or "").strip().lower():
                continue
            filtered_rows.append(row)
        start = (page_num - 1) * page_size
        page_rows = filtered_rows[start:start + page_size]
        return _local_json_record(
            _success_payload(
                {
                    "pageNum": page_num,
                    "pageSize": page_size,
                    "totalSize": len(filtered_rows),
                    "totalPages": (len(filtered_rows) + page_size - 1) // page_size if filtered_rows else 0,
                    "content": page_rows,
                    "records": page_rows,
                    "rows": page_rows,
                    "list": page_rows,
                    "total": len(filtered_rows),
                }
            )
        )

    if path == "/java-api/points/sch/order/queryList":
        submitted = _load_request_payload(request_body)
        page_num, page_size = _page_request_window(submitted)
        return _local_json_record(
            _success_payload(
                {
                    "pageNum": page_num,
                    "pageSize": page_size,
                    "totalSize": 0,
                    "totalPages": 0,
                    "content": [],
                    "records": [],
                    "rows": [],
                    "list": [],
                }
            )
        )

    if path == "/java-api/points/tch/ruleTag/check":
        return _local_json_record(_success_payload([]))

    if path in {"/java-api/points/sch/eduCampus/starRule", "/java-api/points/stu/eduCampus/starRule"}:
        return _local_json_record(_success_payload(_json_deep_copy(DEFAULT_STAR_RULE_ROWS)))

    if path == "/java-api/school/community/work/queryStuWorkList":
        submitted = _load_request_payload(request_body)
        page_num, page_size = _page_request_window(submitted)
        dataset = _build_local_work_dataset(
            store,
            request,
            requested_subject_code=(
                (submitted.get("subjectCode") if isinstance(submitted, dict) else None)
                or (submitted.get("subject_code") if isinstance(submitted, dict) else None)
            ),
            title_filter=(submitted.get("title") if isinstance(submitted, dict) else "") or "",
            page_no=page_num,
            page_size=page_size,
        )
        total_pages = (dataset["total"] + page_size - 1) // page_size if dataset["total"] else 0
        return _local_json_record(
            _success_payload(
                {
                    "pageNum": page_num,
                    "pageSize": page_size,
                    "totalSize": dataset["total"],
                    "totalPages": total_pages,
                    "content": dataset["rows"],
                    "records": dataset["rows"],
                    "rows": dataset["rows"],
                    "list": dataset["rows"],
                    "total": dataset["total"],
                    "workList": dataset["rows"],
                    "stuWorkList": dataset["rows"],
                    "schoolCreateWorkStuList": dataset["rows"],
                }
            )
        )

    if path == "/java-api/school/lessonHourRecord/selectLessonCost":
        submitted = _load_request_payload(request_body)
        page_num, page_size = _page_request_window(submitted)
        return _local_json_record(
            _success_payload(
                {
                    "pageNum": page_num,
                    "pageSize": page_size,
                    "totalSize": 0,
                    "totalPages": 0,
                    "content": [],
                    "records": [],
                    "rows": [],
                    "list": [],
                    "totalContent": {
                        "totalCostMoney": 0,
                        "totalLessonHourNum": 0,
                    },
                }
            )
        )

    if path == "/java-api/school/orderPayRecord/selectOrderPayDetail":
        submitted = _load_request_payload(request_body)
        page_num, page_size = _page_request_window(submitted)
        return _local_json_record(
            _success_payload(
                {
                    "pageNum": page_num,
                    "pageSize": page_size,
                    "totalSize": 0,
                    "totalPages": 0,
                    "content": [],
                    "records": [],
                    "rows": [],
                    "list": [],
                    "totalContent": {
                        "totalIncome": 0,
                        "totalExpenses": 0,
                    },
                }
            )
        )

    if path == "/java-api/school/tch/common/selectByEduCampusId":
        return _local_json_record(_success_payload(_teacher_directory_rows(store)))

    if path == "/java-api/points/stu/order/wearState":
        # Current student exam shell consumes this endpoint as a title resource array
        # and immediately calls `.forEach(...)` on the returned content.
        return _local_json_record(
            _success_payload(
                [
                    {
                        "category": 0,
                        "pictureUrl": "",
                        "cueWord": "",
                    },
                    {
                        "category": 1,
                        "pictureUrl": "",
                        "cueWord": "",
                    },
                    {
                        "category": 3,
                        "pictureUrl": "",
                        "cueWord": "",
                    },
                ]
            )
        )

    if path == "/java-api/points/stu/order/updateHeadState":
        return _local_json_record(_success_payload({"is_update": True}))

    if path == "/java-api/student/stu/checkPwd":
        return _local_json_record(_success_payload(False))

    if path == "/java-api/student/stu/getStuPwdRemind":
        return _local_json_record(_success_payload(False))

    if path == "/java-api/school/stu/setEndDate":
        submitted = _load_request_payload(request_body)
        student_ids = _extract_student_ids(submitted, request)
        for student_id in student_ids:
            end_date = _resolve_student_end_date(
                request,
                submitted,
                store,
                student_id=student_id,
            )
            if end_date:
                store.bulk_upsert_student_overlay([student_id], {"end_date": end_date})
                store.update_student_study_date(student_id, end_date)
        return _local_json_record(
            _success_payload(
                {
                    "is_update": True,
                    "updatedStuIds": student_ids,
                    "successCount": len(student_ids),
                }
            )
        )

    if path == "/java-api/school/stu/batchSetEndDate":
        submitted = _load_request_payload(request_body)
        student_ids = _extract_student_ids(submitted, request)
        for student_id in student_ids:
            end_date = _resolve_student_end_date(
                request,
                submitted,
                store,
                student_id=student_id,
            )
            if end_date:
                store.bulk_upsert_student_overlay([student_id], {"end_date": end_date})
                store.update_student_study_date(student_id, end_date)
        return _local_json_record(
            _success_payload(
                {
                    "is_update": True,
                    "updatedStuIds": student_ids,
                    "successCount": len(student_ids),
                }
            )
        )

    if path in {"/java-api/school/currCls/delete", "/api/delete/class"}:
        submitted = _load_request_payload(request_body)
        class_ids: list[int] = []
        if isinstance(submitted, list):
            _append_int_values(class_ids, submitted)
        if isinstance(submitted, dict):
            for key in ("ids", "classIds", "currClsIds"):
                if key in submitted:
                    _append_int_values(class_ids, submitted[key])
            for key in ("id", "classId", "currClsId"):
                if key in submitted:
                    _append_int_values(class_ids, submitted[key])
        for key in ("ids", "classIds", "currClsIds", "id", "classId", "currClsId"):
            query_value = _first_query_value(request, key)
            if query_value is not None:
                _append_int_values(class_ids, query_value)
        deleted_class_ids: list[int] = []
        for class_id in class_ids:
            if store.upsert_local_class({"id": class_id, "deleted": 1}) is not None:
                deleted_class_ids.append(class_id)
        return _local_json_record(
            _success_payload(
                {
                    "is_delete": True,
                    "deletedClassIds": deleted_class_ids,
                    "updatedClassIds": deleted_class_ids,
                    "successCount": len(deleted_class_ids),
                }
            )
        )

    if path == "/java-api/school/tch/selectCurrCls":
        rows, _ = _build_teacher_class_rows(store, request)
        class_rows = []
        for row in rows:
            class_rows.append(
                {
                    "id": row.get("id"),
                    "currClsId": row.get("id"),
                    "classId": row.get("id"),
                    "name": row.get("name") or "",
                    "className": row.get("name") or "",
                    "subjectNameList": _json_deep_copy(row.get("subjectNameList") or []),
                }
        )
        return _local_json_record(_success_payload(class_rows))

    if path == "/java-api/exam/sch/testExamStu/getList":
        return _local_json_record(_success_payload(_build_exam_student_statistics_content(store, request_body)))

    if path == "/java-api/exam/sch/testExamStu/getPracticeRecords":
        return _local_json_record(_success_payload(_build_competition_practice_records_content(store, request_body)))

    if path == "/java-api/exam/sch/testExamStu/getExamRecords":
        return _local_json_record(_success_payload(_build_competition_exam_records_content(store, request_body)))

    if path == "/java-api/exam/sch/testExamStu/getScoreRankList":
        return _local_json_record(_success_payload(_build_competition_score_rank_rows(store)))

    if path == "/java-api/exam/sch/testStuWrongQuestion/statistics":
        return _local_json_record(_success_payload(_build_competition_wrong_question_statistics_content(store, request_body)))

    if path == "/java-api/exam/sch/testStuWrongQuestion/list":
        return _local_json_record(_success_payload(_build_competition_wrong_question_list_content(store, request_body)))

    if path == "/java-api/exam/sch/testExam/detail":
        return _local_json_record(_success_payload(_build_competition_exam_detail_content(store, request, request_body, practice=False)))

    if path == "/java-api/exam/sch/testExam/practiceDetail":
        return _local_json_record(_success_payload(_build_competition_exam_detail_content(store, request, request_body, practice=True)))

    if path == "/java-api/exam/sch/testStuWrongQuestion/guide":
        return _local_json_record(_success_payload(_build_competition_question_guide_content(store, request, request_body, practice=False)))

    if path == "/java-api/exam/sch/testStuWrongQuestion/practiceGuide":
        return _local_json_record(_success_payload(_build_competition_question_guide_content(store, request, request_body, practice=True)))

    if path == "/java-api/exam/sch/testExam/questionAnalysis":
        return _local_json_record(_success_payload(_build_competition_question_analysis_response(store, request, request_body, practice=False)))

    if path == "/java-api/exam/sch/testExam/practiceAnalysis":
        return _local_json_record(_success_payload(_build_competition_question_analysis_response(store, request, request_body, practice=True)))

    if path == "/java-api/school/stu/queryTimeRecord":
        return _local_json_record(_success_payload(_build_student_time_record_content(store, request, request_body)))

    if path == "/api/stuexam/get/stu/exam/list":
        return _local_json_record(_success_payload(_build_local_stuexam_exam_list_content(store, request, request_body)))

    if path == "/api/stuexam/getStuLessonExamList":
        return _local_json_record(_success_payload(_build_local_stuexam_exam_list_content(store, request, request_body)))

    if path == "/api/stuexam/get/stu/practice/list":
        return _local_json_record(_success_payload(_build_local_stuexam_practice_list_content(store, request, request_body)))

    if path == "/api/stuexam/get/stu/exam/question/list":
        return _local_json_record(_success_payload(_build_local_stuexam_question_list_content(store, request, request_body)))

    if path == "/api/stuexam/get/stu/question/answer":
        return _local_json_record(_success_payload(_build_local_stuexam_question_answer_content(store, request, request_body)))

    if path == "/api/stuexam/check/single/question":
        return _local_json_record(_success_payload(_submit_local_stuexam_answer(store, request, request_body)))

    if path == "/api/stuexam/submit/paper":
        return _local_json_record(_success_payload(_submit_local_stuexam_paper(store, request, request_body)))

    if path == "/api/stuexam/get/exam/result/question/list":
        return _local_json_record(_success_payload(_build_local_stuexam_result_question_list_content(store, request, request_body)))

    if path == "/api/stuexam/getStuWrongQuestionListForNew":
        return _local_json_record(_success_payload(_build_local_stuexam_wrong_question_list_content(store, request, request_body)))

    if path == "/api/stuexam/get/stu/practice/and/record":
        return _local_json_record(_success_payload(_build_local_stu_practice_and_record_content(store, request, request_body)))

    if path == "/api/exam/get/practice/record/question/list/for/tch":
        return _local_json_record(_success_payload(_build_local_practice_record_question_list_content(store, request, request_body)))

    if path == "/api/exam/get/check/paper/question/list":
        return _local_json_record(_success_payload(_build_local_exam_check_paper_question_list_content(store, request, request_body)))

    if path == "/java-api/exam/sch/testExam/getQuestionTypesAndSubjects":
        subject_rows = []
        for subject in _teacher_subject_catalog(store):
            subject_rows.append(
                {
                    "id": subject.get("id"),
                    "subjectId": subject.get("id"),
                    "name": subject.get("name") or subject.get("subject_name") or "",
                    "subjectName": subject.get("name") or subject.get("subject_name") or "",
                }
            )
        return _local_json_record(
            _success_payload(
                {
                    "questionTypes": [],
                    "questionTypeList": [],
                    "subjects": subject_rows,
                    "subjectList": subject_rows,
                }
            )
        )

    if path == "/api/wechat/get/qr/code":
        return _local_json_record(
            _success_payload(
                {
                    "qucodeData": {
                        "data": list(_sample_qr_bytes(store)),
                    }
                }
            )
        )

    if path == "/java-api/student/stu/freshData":
        return _local_json_record(_success_payload(_normalize_student_fresh_data_content(store, None)))

    if path == "/api/delete/stu/user/openid":
        submitted = _load_request_payload(request_body)
        student_ids = _extract_student_ids(submitted, request)
        if student_ids:
            store.bulk_upsert_student_overlay(
                student_ids,
                {
                    "wechat_bound": 0,
                    "parent_wechat": DEFAULT_UNBOUND_TEXT,
                    "wcm_flag": DEFAULT_UNBOUND_TEXT,
                    "open_id": None,
                    "authorizer_openid": None,
                },
            )
        return _local_json_record(_success_payload({"is_delete": True}))

    if path == "/api/delete/user/openid":
        return _local_json_record(_success_payload({"is_delete": True}))

    if path == "/java-api/school/stu/resetPwd":
        submitted = _load_request_payload(request_body)
        student_ids = _extract_student_ids(submitted, request)
        if student_ids:
            store.bulk_upsert_student_overlay(
                student_ids,
                {"last_password_reset_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
            )
        return _local_json_record(_success_payload({"is_update": True}))

    if path == "/java-api/school/stu/quit":
        submitted = _load_request_payload(request_body)
        student_ids = _extract_student_ids(submitted, request)
        if student_ids:
            store.bulk_upsert_student_overlay(student_ids, {"quit": 1, "deleted": 0})
        return _local_json_record(_success_payload({"is_quit": True}))

    if path == "/java-api/school/stu/back":
        submitted = _load_request_payload(request_body)
        student_ids = _extract_student_ids(submitted, request)
        if student_ids:
            store.bulk_upsert_student_overlay(student_ids, {"quit": 0, "deleted": 0})
        return _local_json_record(_success_payload({"is_back": True}))

    if path == "/java-api/school/stu/delete":
        submitted = _load_request_payload(request_body)
        student_ids = _extract_student_ids(submitted, request)
        if student_ids:
            store.bulk_upsert_student_overlay(student_ids, {"deleted": 1, "quit": 0})
        return _local_json_record(_success_payload({"is_delete": True}))

    if path == "/java-api/school/stu/batchDelete":
        submitted = _load_request_payload(request_body)
        student_ids = _extract_student_ids(submitted, request)
        if student_ids:
            store.bulk_upsert_student_overlay(student_ids, {"deleted": 1, "quit": 0})
        return _local_json_record(_success_payload({str(student_id): None for student_id in student_ids}))

    if path == "/java-api/school/stu/updateAuth":
        submitted = _load_request_payload(request_body)
        student_ids = _extract_student_ids(submitted, request)
        updates = _extract_student_overlay_updates(submitted)
        if student_ids and updates:
            store.bulk_upsert_student_overlay(student_ids, updates)
        return _local_json_record(_success_payload({"is_update": True}))

    if path == "/java-api/school/stu/batchUpdateAuth":
        submitted = _load_request_payload(request_body)
        student_ids = _extract_student_ids(submitted, request)
        updates = _extract_student_overlay_updates(submitted)
        if student_ids and updates:
            store.bulk_upsert_student_overlay(student_ids, updates)
        return _local_json_record(_success_payload({"is_update": True}))

    if path == "/java-api/school/stu/queryClsStuMsg":
        submitted = _load_request_payload(request_body)
        student_ids = _extract_student_ids(submitted, request)
        student_id = student_ids[0] if student_ids else 0
        overlay = store.get_student_overlay(student_id)
        return _local_json_record(_success_payload(_build_local_student_auth_content(student_id, overlay)))

    if path == "/java-api/school/stu/selectStudy":
        submitted = _load_request_payload(request_body)
        page_num, page_size = _page_request_window(submitted)
        rows = _build_select_study_rows(store)
        start = (page_num - 1) * page_size
        page_rows = rows[start:start + page_size]
        total_size = len(rows)
        return _local_json_record(
            _success_payload(
                {
                    "pageNum": page_num,
                    "pageSize": page_size,
                    "totalSize": total_size,
                    "totalPages": 0 if total_size == 0 else (total_size + page_size - 1) // page_size,
                    "content": page_rows,
                }
            )
        )

    if path == "/java-api/school/stu/selectStuOut":
        rows = [_build_historical_select_study_entry(store, stu_id) for stu_id in _historical_student_ids(store)]
        submitted = _load_request_payload(request_body)
        page_request = submitted.get("pageRequest") if isinstance(submitted, dict) else {}
        page_num = _parse_int_like((page_request or {}).get("pageNum")) or 1
        page_size = _parse_int_like((page_request or {}).get("pageSize")) or max(len(rows), 1)
        total_size = len(rows)
        return _local_json_record(
            _success_payload(
                {
                    "pageNum": page_num,
                    "pageSize": page_size,
                    "totalSize": total_size,
                    "totalPages": 0 if total_size == 0 else (total_size + page_size - 1) // page_size,
                    "content": rows,
                }
            )
        )

    if path == "/java-api/school/stu/create":
        submitted = _load_json_body(request_body)
        created = store.create_local_student(submitted)
        # Auto-provision a profiles row so the new student can sign in immediately.
        try:
            password_hash = _hash_login_password("123456")
            token = _mint_local_login_token(store, prefix="local-student")
            store.upsert_student_login_profile(
                created,
                password_hash=password_hash,
                token=token,
                login_path=STUDENT_LOGIN_PATH,
            )
        except Exception as exc:
            print(f"[create_local_student] profile provisioning skipped: {exc}")
        payload = {
            "success": True,
            "content": {
                "id": created["id"],
                "studentId": created["id"],
                "name": created["name"],
                "realName": created["realname"],
            },
            "error": {"message": "", "code": ""},
        }
        return {
            "status": 200,
            "content_type": "application/json; charset=utf-8",
            "headers": {"content-type": "application/json; charset=utf-8"},
            "body": json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        }

    if path == "/api/admin/get/getAdminSubjectListWithOutPageInfo":
        payload = {
            "success": True,
            "content": {"subject_list": _build_admin_subject_list(store)},
            "error": {"message": "", "code": ""},
        }
        return {
            "status": 200,
            "content_type": "application/json; charset=utf-8",
            "headers": {"content-type": "application/json; charset=utf-8"},
            "body": json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        }

    if path == "/api/admin/get/school/curriculum/list":
        rows = _build_admin_curriculum_rows(store, request)
        page_no_raw = _first_query_value(request, "page_no") or "1"
        page_size_raw = _first_query_value(request, "page_size") or "20"
        page_no = int(page_no_raw) if page_no_raw.isdigit() else 1
        page_size = int(page_size_raw) if page_size_raw.isdigit() else 20
        page_no = max(page_no, 1)
        page_size = max(page_size, 1)
        start = (page_no - 1) * page_size
        payload = {
            "success": True,
            "content": {
                "curriculum_list": rows[start:start + page_size],
                "total": len(rows),
                "page_no": page_no,
                "page_size": page_size,
            },
            "error": {"message": "", "code": ""},
        }
        return {
            "status": 200,
            "content_type": "application/json; charset=utf-8",
            "headers": {"content-type": "application/json; charset=utf-8"},
            "body": json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        }

    if path == "/java-api/school/edu/getPlatformRights":
        teacher_profile = store.get_profile("teacher") or {}
        school_info = (teacher_profile.get("fresh_auth") or {}).get("schoolInfo") or {}
        user_info = (teacher_profile.get("fresh_auth") or {}).get("userInfo") or {}
        payload = {
            "success": True,
            "content": {
                "eduName": school_info.get("eduName") or school_info.get("name") or "",
                "eduDomain": school_info.get("eduDomain") or "",
                "offTime": school_info.get("offTime") or "",
                "activeStuNum": 0,
                "maxStudentNum": 0,
                "platformTchNum": 0,
                "maxTeacherNum": 0,
                "currentCampusNum": 1 if school_info else 0,
                "maxCampusNum": 1 if school_info else 0,
                "stuRemainTime": 0,
                "businessVersion": 0,
                "subjectPermissions": [],
                "eduContractList": [],
                "referralCode": user_info.get("referralCode") or "",
                "unusedCouponAmount": 0,
            },
            "error": {"message": "", "code": ""},
        }
        return {
            "status": 200,
            "content_type": "application/json; charset=utf-8",
            "headers": {"content-type": "application/json; charset=utf-8"},
            "body": json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        }

    if path == "/api/tch/get/tch/cpp/lesson/oj/problem/list":
        return {
            "status": 200,
            "content_type": "application/json; charset=utf-8",
            "headers": {"content-type": "application/json; charset=utf-8"},
            "body": json.dumps(EMPTY_CPP_PROBLEM_LIST_RESPONSE, ensure_ascii=False).encode("utf-8"),
        }

    if path == "/api/tchWorkSelfRemark/get":
        return {
            "status": 200,
            "content_type": "application/json; charset=utf-8",
            "headers": {"content-type": "application/json; charset=utf-8"},
            "body": json.dumps(
                {
                    "success": True,
                    "content": {"tchWorkSelfRemarkList": store.list_tch_work_self_remarks()},
                    "error": {"message": "", "code": ""},
                },
                ensure_ascii=False,
            ).encode("utf-8"),
        }

    if path == "/api/tchWorkSelfRemark/createOrUpdate":
        payload = parse_qs(request_body.decode("utf-8", errors="ignore"), keep_blank_values=True)
        remark = (payload.get("remark") or [""])[0].strip()
        remark_id = (payload.get("remark_id") or [None])[0]
        if not remark:
            return {
                "status": 200,
                "content_type": "application/json; charset=utf-8",
                "headers": {"content-type": "application/json; charset=utf-8"},
                "body": json.dumps(
                    {
                        "success": False,
                        "content": None,
                        "error": {"message": "remark is required", "code": "ValidationError"},
                    },
                    ensure_ascii=False,
                ).encode("utf-8"),
            }
        saved = store.save_tch_work_self_remark(remark, remark_id=remark_id)
        return {
            "status": 200,
            "content_type": "application/json; charset=utf-8",
            "headers": {"content-type": "application/json; charset=utf-8"},
            "body": json.dumps(
                {
                    "success": True,
                    "content": saved,
                    "error": {"message": "", "code": ""},
                },
                ensure_ascii=False,
            ).encode("utf-8"),
        }

    if path == "/api/tchWorkSelfRemark/delete":
        payload = parse_qs(request_body.decode("utf-8", errors="ignore"), keep_blank_values=True)
        remark_id = (payload.get("remark_id") or [""])[0]
        deleted = store.delete_tch_work_self_remark(remark_id)
        return {
            "status": 200,
            "content_type": "application/json; charset=utf-8",
            "headers": {"content-type": "application/json; charset=utf-8"},
            "body": json.dumps(
                {
                    "success": True,
                    "content": {"deleted": deleted},
                    "error": {"message": "", "code": ""},
                },
                ensure_ascii=False,
            ).encode("utf-8"),
        }

    if path in TEACHING_PLAN_EMPTY_ENDPOINTS:
        payload = json.loads(json.dumps(TEACHING_PLAN_EMPTY_ENDPOINTS[path], ensure_ascii=False))
        if path == "/api/tch/getTeachingPlanList":
            page_no = _first_query_value(request, "page_no")
            page_size = _first_query_value(request, "page_size")
            if page_no and page_no.isdigit():
                payload["content"]["page_no"] = int(page_no)
            if page_size and page_size.isdigit():
                payload["content"]["page_size"] = int(page_size)
        return {
            "status": 200,
            "content_type": "application/json; charset=utf-8",
            "headers": {"content-type": "application/json; charset=utf-8"},
            "body": json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        }

    if path == "/java-api/school/currMat/detail":
        curr_mat_id = None
        try:
            payload = json.loads(request_body.decode("utf-8")) if request_body else {}
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            value = payload.get("currMatId")
            if isinstance(value, int):
                curr_mat_id = value
            elif isinstance(value, str) and value.strip().isdigit():
                curr_mat_id = int(value.strip())
        if curr_mat_id is None:
            curr_mat_id = _extract_curr_mat_id_from_request(request)
        tch_plan_id = None
        if isinstance(payload, dict):
            for key in ("tchPlanId", "teachingPlanId"):
                value = payload.get(key)
                if isinstance(value, int):
                    tch_plan_id = value
                    break
                if isinstance(value, str) and value.strip().isdigit():
                    tch_plan_id = int(value.strip())
                    break
        if tch_plan_id is None:
            tch_plan_id = _extract_teaching_plan_id_from_request(request)
        material = None
        if curr_mat_id is not None:
            material = store.find_curriculum_material(curr_mat_id)
        else:
            material = _default_teacher_curriculum_material(store)
        if material is None:
            material = _default_teacher_curriculum_material(store)
        if material is not None:
            if curr_mat_id is None:
                raw_material_id = material.get("id")
                if isinstance(raw_material_id, int):
                    curr_mat_id = raw_material_id
                elif isinstance(raw_material_id, str) and raw_material_id.strip().isdigit():
                    curr_mat_id = int(raw_material_id.strip())
            if curr_mat_id is not None:
                detail = {
                    "curriculumMaterial": {
                        "id": material.get("id"),
                        "subjectId": material.get("subject_id"),
                        "curriculumId": material.get("curriculum_id"),
                        "eduId": material.get("educational_institution_id"),
                        "title": material.get("title") or "",
                        "sortNum": material.get("sort_num"),
                        "remarks": material.get("remarks"),
                        "createdTime": material.get("created_time"),
                        "imgUrl": material.get("img_url") or "",
                        "desc": material.get("desc") or "",
                        "pptUrl": material.get("ppt_url") or "",
                        "stuNoteUrl": material.get("stu_note_url") or "",
                        "knowledgePointUrl": material.get("knowledge_point_url") or "",
                        "videoUrl": material.get("video_url") or "",
                        "lessionPlanUrl": material.get("lession_plan_url") or "",
                        "trainVideoUrl": material.get("train_video_url") or "",
                        "exampleVideoUrl": material.get("exampal_video_url") or "",
                        "assemblePitcureState": material.get("assemble_pitcure_state"),
                        "assemblePitcure": material.get("assemble_pitcure"),
                        "assemblePitcurePdf": material.get("assemble_pitcure_pdf"),
                        "totalStorage": material.get("total_storage"),
                        "exampleWorkUrl": material.get("exampal_work_url") or "",
                        "teachTemplateUrl": material.get("teach_template_url") or "",
                        "homeTemplateUrl": material.get("home_template_url") or "",
                        "otherMaterialUrl": material.get("other_meterial_url") or "",
                        "isPost": material.get("is_post"),
                    },
                    "tchPlanInfo": _teaching_plan_template_info(
                        store,
                        request,
                        curr_mat_id=curr_mat_id,
                        teaching_plan_id=tch_plan_id,
                    ),
                }
                return {
                    "status": 200,
                    "content_type": "application/json; charset=utf-8",
                    "headers": {"content-type": "application/json; charset=utf-8"},
                    "body": json.dumps(
                        {"success": True, "content": detail, "error": {"message": "", "code": ""}},
                        ensure_ascii=False,
                    ).encode("utf-8"),
                }
    return None


def _postprocess_json_payload(store: MirrorStore, request: Request, payload: dict[str, Any]) -> dict[str, Any]:
    payload = _merge_local_students_into_payload(store, request, payload)
    if not payload.get("success", True):
        return payload

    content = payload.get("content")
    if not isinstance(content, dict):
        return payload

    if request.url.path in {"/api/get/school/subject/list", "/api/get/zone/school/subject/list"}:
        content["subjectList"] = _merge_subject_rows(content.get("subjectList"), _teacher_subject_catalog(store))
    elif request.url.path == "/api/get/campus/subject/list":
        content["campusSubjectList"] = _merge_subject_rows(
            content.get("campusSubjectList"),
            _teacher_subject_catalog(store),
        )
    elif request.url.path == "/api/get/homepage":
        homepage_content = _build_homepage_content(store, request)
        content["schoolInfo"] = _merge_dict_defaults(content.get("schoolInfo"), homepage_content["schoolInfo"])
        content["userInfo"] = _merge_dict_defaults(content.get("userInfo"), homepage_content["userInfo"])
        content["homepageData"] = _merge_dict_defaults(content.get("homepageData"), homepage_content["homepageData"])
        content["homepage"] = _merge_dict_defaults(content.get("homepage"), homepage_content["homepage"])
        if content.get("imgUrl") in (None, ""):
            content["imgUrl"] = homepage_content["imgUrl"]
    return payload


def _default_profile_state(
    *,
    username: str,
    token: str,
    role: str,
    user_info: dict[str, Any],
    school_info: dict[str, Any],
    role_list: list[Any] | None = None,
) -> dict[str, Any]:
    permissions = permission_tree_for_role(role)
    return {
        "user": {
            "username": user_info.get("realName") or username,
            "token": token,
            "adminUserName": username if role == "admin" else "",
            "adminUserId": user_info.get("id") if role == "admin" else None,
            "adminToken": token if role == "admin" else "",
            "isSuperAdmin": role == "admin",
            "is_principal": role == "admin",
            "roleList": role_list or [],
            "selected_schools": [],
            "permisionList": permissions,
            "adminpermisionList": permissions if role == "admin" else [],
            "userInfo": user_info,
            "schoolInfo": school_info,
            "identity": 1,
            "eduTchList": [],
            "isAdmin": role == "admin",
            "isTeacher": role == "teacher",
            "isStudent": False,
        }
    }


def _store_default_staff_profile(
    store: MirrorStore,
    *,
    profile_name: str,
    username: str,
    token: str,
    user_info: dict[str, Any],
    school_info: dict[str, Any],
    role_list: list[Any] | None = None,
) -> None:
    role = "admin" if profile_name == "admin" else "teacher"
    store.store_profile(
        profile_name=profile_name,
        username=username,
        password_hash=_hash_login_password("123456"),
        login_path=TEACHER_LOGIN_PATH,
        token=token,
        login_content={"authTree": json.dumps({"children": []}, ensure_ascii=False), "token": token},
        fresh_auth={
            "identity": 1,
            "userInfo": user_info,
            "schoolInfo": school_info,
            "roleList": role_list or [],
        },
        vuex_state=_default_profile_state(
            username=username,
            token=token,
            role=role,
            user_info=user_info,
            school_info=school_info,
            role_list=role_list,
        ),
    )


def _ensure_default_local_runtime_materials(store: MirrorStore) -> None:
    """Provide explicit local course materials for the seeded offline class."""
    store.upsert_local_curriculum_snapshot(
        {
            "id": 501,
            "subject_id": 1,
            "title": "AI 创造启蒙",
            "number_of_courses": 2,
            "img_url": "/_site/courses/images/robot-camp.webp",
        }
    )
    for material in (
        {
            "id": 7001,
            "subject_id": 1,
            "curriculum_id": 501,
            "title": "AI 创造启蒙：智能小车",
            "sort_num": 1,
            "desc": "认识传感器与顺序控制，完成第一辆智能小车。",
            "img_url": "/_site/courses/images/robot-camp.webp",
            "ppt_url": "/_site/workspace/ppt-demo.html?lesson=smart-car",
            "teach_template_url": "/_site/workspace/ppt-demo.html?lesson=smart-car",
            "exampal_work_url": "/_site/workspace/ppt-demo.html?lesson=smart-car",
            "home_template_url": "/_site/workspace/ppt-demo.html?lesson=smart-car",
        },
        {
            "id": 7002,
            "subject_id": 1,
            "curriculum_id": 501,
            "title": "AI 创造启蒙：机器人任务",
            "sort_num": 2,
            "desc": "组合机械结构与程序控制，完成协作挑战。",
            "img_url": "/_site/courses/images/lego-course.webp",
            "ppt_url": "/_site/workspace/ppt-demo.html?lesson=robot-mission",
            "teach_template_url": "/_site/workspace/ppt-demo.html?lesson=robot-mission",
            "exampal_work_url": "/_site/workspace/ppt-demo.html?lesson=robot-mission",
            "home_template_url": "/_site/workspace/ppt-demo.html?lesson=robot-mission",
        },
    ):
        store.upsert_local_curriculum_material_snapshot(material)


def _ensure_default_local_runtime_data(store: MirrorStore) -> None:
    """Seed a brand-new local runtime with usable role and class data."""
    if store.list_profiles():
        teacher_profile = store.get_profile("teacher") or {}
        if teacher_profile.get("token") == "local-teacher-token":
            _ensure_default_local_runtime_materials(store)
        return

    campus_id = 851
    school_info = {
        "id": 834,
        "eduCampusId": campus_id,
        "name": "乐启享机器人",
        "domain": "lqx",
        "offTime": "2099-12-31 23:59:59",
        "maxTeacherNum": 20,
        "maxStudentNum": 10000,
        "stuRemainTime": 99999,
        "authorize": False,
        "isTry": False,
        "questionBankPermission": True,
        "ojPermission": True,
        "pointAuth": True,
        "prepareContentAuth": True,
        "stuZoneAuth": True,
        "typingPlanetAuth": True,
        "themeColor": "#1778FF",
    }
    store.upsert_local_campus(
        {
            "id": campus_id,
            "name": "乐启享机器人中心校区",
            "address": "宜昌市猇亭区金岭路9-1号",
            "phone": "18164173640",
            "state": 1,
        }
    )
    _store_default_staff_profile(
        store,
        profile_name="admin",
        username="18164173640",
        token="local-admin-token",
        role_list=[5],
        school_info=school_info,
        user_info={
            "id": 3394,
            "userId": 3394,
            "name": "18164173640",
            "realName": "超级管理员",
            "phoneNum": "18164173640",
            "principal": True,
            "state": "在职",
            "eduCampusId": campus_id,
        },
    )
    _store_default_staff_profile(
        store,
        profile_name="teacher",
        username="zhaosenlin",
        token="local-teacher-token",
        role_list=[1],
        school_info=school_info,
        user_info={
            "id": 12385,
            "userId": 12385,
            "name": "zhaosenlin",
            "realName": "森林老师",
            "phoneNum": "18164173640",
            "principal": False,
            "state": "在职",
            "eduCampusId": campus_id,
        },
    )

    student = store.create_local_student(
        {
            "eduCampusId": campus_id,
            "headimgUrl": "/_external/wugecdn.steam.fun/resources/static/homepage/nanxueshengtouxiang-min.png",
            "normalState": "1",
            "name": "lbschenmuran",
            "realName": "陈沐然",
            "sex": "M",
            "parentAPhoneNum": "18164173640",
            "schoolName": "乐启享机器人",
            "grade": "小学",
            "leader": "森林老师",
            "remark": "默认本地运行学员",
            "studyDate": "2026-07-01",
        }
    )
    student_profile = store.upsert_student_login_profile(
        student,
        password_hash=_hash_login_password("123456"),
        token="local-student-token",
        login_path=STUDENT_LOGIN_PATH,
    )
    store.store_profile(
        profile_name="student",
        username="lbschenmuran",
        password_hash=_hash_login_password("123456"),
        login_path=STUDENT_LOGIN_PATH,
        token="local-student-token",
        login_content=student_profile["login_content"],
        fresh_auth=student_profile["fresh_auth"],
        vuex_state=student_profile["vuex_state"],
    )
    store.delete_profile(str(student_profile.get("profile_name") or ""))

    class_id = 143567
    store.upsert_local_class(
        {
            "id": class_id,
            "className": "乐启享 AI 创造周六班",
            "campusId": campus_id,
            "lecturer_id": 12385,
            "lecturer_name": "森林老师",
            "curriculum_class_type": 1,
            "teaching_type": 1,
            "week_json": [6],
            "week_str": "周六",
            "time_str": "09:00-10:30",
            "subjectIdArr": [1],
            "curriculumIdArr": [501],
            "end_class_state": 0,
        }
    )
    student_id = int(student["id"])
    store.upsert_local_class_student_relation(
        class_id=class_id,
        student_user_id=student_id,
        in_class_date="2026-07-01",
    )

    _ensure_default_local_runtime_materials(store)

    for index, payload in enumerate(
        (
            {
                "id": 5182933,
                "curriculum_meterial_id": 7001,
                "class_date": "2026-07-04",
                "start_class_date": "2026-07-04 09:00:00",
                "end_class_date": "2026-07-04 10:30:00",
                "sign_state": 1,
                "sign_state_new": 1,
                "sign_date": "2026-07-04 10:30:00",
                "custom_lesson_title": "AI 创造启蒙第一课",
            },
            {
                "id": 5182934,
                "curriculum_meterial_id": 7002,
                "class_date": "2026-07-11",
                "start_class_date": "2026-07-11 09:00:00",
                "end_class_date": "2026-07-11 10:30:00",
                "sign_state": 0,
                "sign_state_new": 0,
                "sign_date": "",
                "custom_lesson_title": "机器人结构与程序控制",
            },
        ),
        start=1,
    ):
        plan = store.upsert_local_teaching_plan(
            {
                **payload,
                "curriculum_class_id": class_id,
                "educational_institution_campus_id": campus_id,
                "lecturer_id": 12385,
                "lecturer_name": "森林老师",
                "subject_id": 1,
                "curriculum_id": 501,
                "sort_num": index,
                "cost_lesson_hour": 1,
            }
        )
        if plan is not None:
            store.upsert_local_teaching_plan_student_relation(
                teaching_plan_id=plan["id"],
                student_user_id=student_id,
                sign_state=payload["sign_state"],
                sign_date=payload["sign_date"],
                cost_lesson_hour=1,
            )


def create_app(root: Path, *, allow_live_proxy: bool = True) -> FastAPI:
    store = MirrorStore(root)
    _ensure_default_local_runtime_data(store)
    app = FastAPI(title="steam.fun local mirror")

    @app.get("/__mirror__/health")
    def health() -> dict[str, Any]:
        with sqlite3.connect(store.db_path) as connection:
            profile_count = connection.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
            route_count = connection.execute("SELECT COUNT(*) FROM routes").fetchone()[0]
            api_count = connection.execute("SELECT COUNT(*) FROM api_responses").fetchone()[0]
            asset_count = connection.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        return {
            "profiles": profile_count,
            "routes": route_count,
            "api_responses": api_count,
            "assets": asset_count,
            "allow_live_proxy": allow_live_proxy,
        }

    @app.get("/")
    def marketing_homepage(request: Request) -> Response:
        response = Response(
            content=render_marketing_homepage(request).encode("utf-8"),
            media_type="text/html",
        )
        response.headers["cache-control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["pragma"] = "no-cache"
        response.headers["expires"] = "0"
        return response

    @app.get("/_site/homepage/{asset_path:path}")
    def homepage_static_asset(asset_path: str) -> Response:
        candidate = homepage_asset_path(asset_path)
        if candidate is None:
            return Response(status_code=404)
        return _no_store_response(_static_response_or_404(candidate, expected_asset_path=asset_path))

    @app.get("/_site/courses/{asset_path:path}")
    def courses_static_asset(asset_path: str) -> Response:
        if asset_path in ("", "/"):
            index_path = COURSES_ASSET_ROOT / "index.html"
            if index_path.is_file():
                return _public_html_response(index_path)
        candidate = courses_asset_path(asset_path)
        if candidate is not None:
            if candidate.suffix.lower() in {".html", ".htm"}:
                return _public_html_response(candidate)
            return _no_store_response(_static_response_or_404(candidate, expected_asset_path=asset_path))
        return Response(status_code=404)

    @app.get("/courses")
    @app.get("/courses/")
    @app.get("/courses.html")
    def public_courses_page() -> Response:
        index_path = COURSES_ASSET_ROOT / "index.html"
        if not index_path.is_file():
            return Response(status_code=404)
        return _public_html_response(index_path)

    @app.get("/course-detail")
    @app.get("/course-detail.html")
    def public_course_detail_page() -> Response:
        detail_path = COURSES_ASSET_ROOT / "course-detail.html"
        if not detail_path.is_file():
            return Response(status_code=404)
        return _public_html_response(detail_path)

    @app.get("/_site/competitions/{asset_path:path}")
    def competitions_static_asset(asset_path: str) -> Response:
        if asset_path in ("", "/"):
            if COMPETITIONS_ASSET_INDEX.is_file():
                return _public_html_response(COMPETITIONS_ASSET_INDEX)
        candidate = competitions_asset_path(asset_path)
        if candidate is not None:
            if candidate.suffix.lower() in {".html", ".htm"}:
                return _public_html_response(candidate)
            return _no_store_response(_static_response_or_404(candidate, expected_asset_path=asset_path))
        return Response(status_code=404)

    @app.get("/competitions.html")
    def competitions_page() -> Response:
        if not COMPETITIONS_ASSET_INDEX.is_file():
            return Response(status_code=404)
        return _public_html_response(COMPETITIONS_ASSET_INDEX)

    @app.get("/competitions")
    def competitions_alias() -> Response:
        return Response(status_code=302, headers={"Location": "/competitions.html"})

    @app.get("/_site/workspace/{asset_path:path}")
    def workspace_static_asset(asset_path: str) -> Response:
        candidate = workspace_asset_path(asset_path)
        if candidate is None:
            return Response(status_code=404)
        return _static_response_or_404(candidate, expected_asset_path=asset_path)

    @app.post(TEACHER_LOGIN_PATH)
    async def teacher_login(request: Request) -> Response:
        payload = await request.json()
        return _local_login_response(store, payload, expected_login_path=TEACHER_LOGIN_PATH)

    @app.post(STUDENT_LOGIN_PATH)
    async def student_login(request: Request) -> Response:
        payload = await request.json()
        return _local_login_response(store, payload, expected_login_path=STUDENT_LOGIN_PATH)

    @app.get("/workspace/{requested_role}")
    def workspace_page(requested_role: str, request: Request) -> Response:
        if requested_role not in {"admin", "teacher"}:
            return Response(status_code=404)
        profile = _resolve_authenticated_profile(store, request)
        if profile is None:
            return RedirectResponse(
                url=f"/login?next={quote(request.url.path, safe='')}",
                status_code=303,
            )
        profile_role = _profile_role(profile.get("profile_name"), profile)
        return RedirectResponse(
            url=_default_frontend_route_for_role(profile_role) or "/login",
            status_code=303,
        )

    @app.get("/api/workspace/bootstrap")
    def workspace_bootstrap(request: Request) -> Response:
        profile = _resolve_authenticated_profile(store, request)
        if profile is None:
            return JSONResponse(
                {"success": False, "error": {"code": "AuthRequired", "message": "请先登录"}},
                status_code=401,
            )
        role = _profile_role(profile.get("profile_name"), profile)
        if role not in {"admin", "teacher"}:
            return JSONResponse(
                {"success": False, "error": {"code": "Forbidden", "message": "无权访问该工作台"}},
                status_code=403,
            )
        return JSONResponse(_success_payload(build_workspace_payload(store, profile)))

    @app.get("/api/workspace/teachers")
    def workspace_teacher_list(request: Request, query: str = "") -> Response:
        authorization_error = _workspace_role_error(store, request, frozenset({"admin"}))
        if authorization_error is not None:
            return authorization_error
        normalized_query = str(query or "").strip().lower()
        rows = _staff_account_rows(store, include_admin=False, include_subjects=True)
        if normalized_query:
            rows = [
                row
                for row in rows
                if normalized_query in str(row.get("name") or "").lower()
                or normalized_query in str(row.get("realName") or "").lower()
            ]
        return JSONResponse(_success_payload({"records": rows, "total": len(rows)}))

    @app.post("/api/workspace/teachers")
    async def workspace_teacher_create(request: Request) -> Response:
        authorization_error = _workspace_role_error(store, request, frozenset({"admin"}))
        if authorization_error is not None:
            return authorization_error
        submitted = await request.json()
        username = str(submitted.get("name") or submitted.get("username") or "").strip()
        password = str(submitted.get("password") or "")
        if not username or len(password) < 6:
            return JSONResponse(
                {
                    "success": False,
                    "error": {"code": "ValidationError", "message": "账号不能为空，初始密码至少 6 位"},
                },
                status_code=400,
            )
        if _find_staff_profile(store, username=username, include_admin=True) is not None:
            return JSONResponse(
                {"success": False, "error": {"code": "Conflict", "message": "该教师账号已存在"}},
                status_code=409,
            )
        stored = _upsert_staff_account_profile(store, request, submitted)
        return JSONResponse(_success_payload(_staff_account_row(store, stored, include_subjects=True)))

    @app.patch("/api/workspace/teachers/{user_id}")
    async def workspace_teacher_update(user_id: int, request: Request) -> Response:
        authorization_error = _workspace_role_error(store, request, frozenset({"admin"}))
        if authorization_error is not None:
            return authorization_error
        existing = _find_staff_profile(store, user_id=user_id, include_admin=False)
        if existing is None:
            return JSONResponse(
                {"success": False, "error": {"code": "NotFound", "message": "教师账号不存在"}},
                status_code=404,
            )
        submitted = await request.json()
        submitted["userId"] = user_id
        stored = _upsert_staff_account_profile(store, request, submitted)
        return JSONResponse(_success_payload(_staff_account_row(store, stored, include_subjects=True)))

    @app.post("/api/workspace/teachers/{user_id}/password")
    async def workspace_teacher_password(user_id: int, request: Request) -> Response:
        authorization_error = _workspace_role_error(store, request, frozenset({"admin"}))
        if authorization_error is not None:
            return authorization_error
        profile = _find_staff_profile(store, user_id=user_id, include_admin=False)
        submitted = await request.json()
        password = str(submitted.get("password") or "")
        if profile is None:
            return JSONResponse(
                {"success": False, "error": {"code": "NotFound", "message": "教师账号不存在"}},
                status_code=404,
            )
        if len(password) < 6:
            return JSONResponse(
                {"success": False, "error": {"code": "ValidationError", "message": "新密码至少 6 位"}},
                status_code=400,
            )
        stored = _persist_local_profile(
            store,
            profile_name=str(profile.get("profile_name") or ""),
            username=str(profile.get("username") or ""),
            password_hash=_hash_login_password(password),
            token=str(profile.get("token") or ""),
            login_content=_json_deep_copy(profile.get("login_content") or {}),
            fresh_auth=_json_deep_copy(profile.get("fresh_auth") or {}),
            vuex_state=_json_deep_copy(profile.get("vuex_state") or {}),
        )
        return JSONResponse(_success_payload(_staff_account_row(store, stored)))

    @app.delete("/api/workspace/teachers/{user_id}")
    def workspace_teacher_delete(user_id: int, request: Request) -> Response:
        authorization_error = _workspace_role_error(store, request, frozenset({"admin"}))
        if authorization_error is not None:
            return authorization_error
        profile = _find_staff_profile(store, user_id=user_id, include_admin=False)
        if profile is None:
            return JSONResponse(
                {"success": False, "error": {"code": "NotFound", "message": "教师账号不存在"}},
                status_code=404,
            )
        if str(profile.get("profile_name") or "") == "teacher":
            return JSONResponse(
                {"success": False, "error": {"code": "ProtectedAccount", "message": "系统教师账号不能删除"}},
                status_code=409,
            )
        referenced_classes = [
            row
            for row in store.list_classes()
            if not bool(_coerce_int(row.get("deleted")))
            and user_id
            in {
                _coerce_int(row.get("lecturer_id") or row.get("lecturerId")),
                _coerce_int(row.get("assistant_teacher_id") or row.get("assistantTeacherId")),
            }
        ]
        if referenced_classes:
            return JSONResponse(
                {
                    "success": False,
                    "error": {"code": "TeacherInUse", "message": "该教师仍关联班级，请先调整班级教师"},
                },
                status_code=409,
            )
        deleted = store.delete_profile(str(profile.get("profile_name") or ""))
        return JSONResponse(_success_payload({"deleted": deleted}))

    def workspace_campus_rows() -> list[dict[str, Any]]:
        staff_rows = _staff_account_rows(store, include_admin=False)
        class_rows = store.list_classes()
        rows: list[dict[str, Any]] = []
        for campus in store.list_campuses():
            campus_id = _coerce_int(campus.get("id") or campus.get("eduCampusId") or campus.get("dept_id")) or 0
            current = _json_deep_copy(campus)
            current["id"] = campus_id
            current["name"] = str(
                current.get("name") or current.get("campusName") or current.get("dept_name") or f"校区 {campus_id}"
            ).strip()
            current["teacherCount"] = sum(
                1
                for row in staff_rows
                if campus_id in _extract_campus_ids(row.get("eduCampusIdList") or row.get("eduCampusId"))
            )
            current["classCount"] = sum(
                1
                for row in class_rows
                if _coerce_int(
                    row.get("educational_institution_campus_id") or row.get("eduCampusId") or row.get("campusId")
                ) == campus_id
                and not bool(_coerce_int(row.get("deleted")))
            )
            rows.append(current)
        return rows

    @app.get("/api/workspace/campuses")
    def workspace_campus_list(request: Request) -> Response:
        authorization_error = _workspace_role_error(store, request, frozenset({"admin"}))
        if authorization_error is not None:
            return authorization_error
        rows = workspace_campus_rows()
        return JSONResponse(_success_payload({"records": rows, "total": len(rows)}))

    @app.post("/api/workspace/campuses")
    async def workspace_campus_create(request: Request) -> Response:
        authorization_error = _workspace_role_error(store, request, frozenset({"admin"}))
        if authorization_error is not None:
            return authorization_error
        submitted = await request.json()
        try:
            row = store.upsert_local_campus(submitted)
        except ValueError as exc:
            return JSONResponse(
                {"success": False, "error": {"code": "ValidationError", "message": str(exc)}},
                status_code=400,
            )
        return JSONResponse(_success_payload(row))

    @app.patch("/api/workspace/campuses/{campus_id}")
    async def workspace_campus_update(campus_id: int, request: Request) -> Response:
        authorization_error = _workspace_role_error(store, request, frozenset({"admin"}))
        if authorization_error is not None:
            return authorization_error
        submitted = await request.json()
        submitted["id"] = campus_id
        try:
            row = store.upsert_local_campus(submitted)
        except ValueError as exc:
            return JSONResponse(
                {"success": False, "error": {"code": "ValidationError", "message": str(exc)}},
                status_code=400,
            )
        return JSONResponse(_success_payload(row))

    @app.api_route("/api/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
    @app.api_route("/java-api/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
    async def replay_api(full_path: str, request: Request) -> Response:
        authorization_error = _api_authorization_error(store, request)
        if authorization_error is not None:
            return authorization_error

        if request.url.path == "/java-api/auth/sch/freshAuthData" or request.url.path == "/java-api/student/stu/freshData" or request.url.path == "/java-api/school/tch/freshData":
            return _local_fresh_auth_response(store, request)

        if request.url.path in NON_CORE_DASHBOARD_API_PATHS:
            return _non_core_dashboard_empty_response()
        # Non-core points/stu endpoints (personalSoa, stuStar, etc.) would 401 against the upstream mirror
        # for local_student_* profiles because their auth tokens are JWT-shaped local secrets. Serve an empty
        # success response so the SPA does not treat them as auth failures and bounce back to /login.
        if request.url.path.startswith("/java-api/points/stu/") and request.url.path not in {
            "/java-api/points/stu/eduCampus/starRule",
            "/java-api/points/stu/order/updateHeadState",
            "/java-api/points/stu/order/wearState",
        }:
            return _non_core_dashboard_empty_response()

        request_body = await request.body()
        resolved_profile = _resolve_profile(store, request)
        profile_name = resolved_profile["profile_name"] if resolved_profile else _resolve_profile_name(store, request)
        profile_role = _profile_role(profile_name, resolved_profile)
        live_url = f"{BASE_URL}{request.url.path}"
        if request.url.query:
            live_url = f"{live_url}?{request.url.query}"

        record = None
        candidate_urls = _api_lookup_url_variants(live_url)
        lookup_profiles: list[str] = []
        for candidate_profile in (profile_name, profile_role):
            if candidate_profile and candidate_profile not in lookup_profiles:
                lookup_profiles.append(candidate_profile)
        for lookup_profile in lookup_profiles:
            for candidate_url in candidate_urls:
                candidate_record = store.lookup_api_response(
                    lookup_profile,
                    method=request.method,
                    url=candidate_url,
                    request_body=request_body,
                )
                if candidate_record is None or _record_contains_invalid_token(candidate_record):
                    continue
                record = candidate_record
                if record is not None:
                    break
            if record is not None:
                break

        skip_cross_profile_lookup = (
            (_is_teacher_like_role(profile_role) and request.url.path in LOCAL_TEACHER_FALLBACK_PATHS)
            or (profile_role == "student" and request.url.path in LOCAL_STUDENT_FALLBACK_PATHS)
        )
        if record is None and not skip_cross_profile_lookup:
            for fallback_profile in ("public", "teacher", "student"):
                if fallback_profile in lookup_profiles:
                    continue
                for candidate_url in candidate_urls:
                    candidate_record = store.lookup_api_response(
                        fallback_profile,
                        method=request.method,
                        url=candidate_url,
                        request_body=request_body,
                    )
                    if candidate_record is None or _record_contains_invalid_token(candidate_record):
                        continue
                    record = candidate_record
                    if record is not None:
                        break
                if record is not None:
                    break

        if (
            record is not None
            and record["status"] == 401
            and request.url.path == "/java-api/school/edu/getPlatformRights"
        ):
            record = None

        teacher_fallback_path = _is_teacher_like_role(profile_role) and request.url.path in LOCAL_TEACHER_FALLBACK_PATHS
        student_fallback_path = profile_role == "student" and request.url.path in LOCAL_STUDENT_FALLBACK_PATHS
        prefer_local_fallback = (
            (_is_teacher_like_role(profile_role) and request.url.path in LOCAL_TEACHER_PREFER_LOCAL_FALLBACK_PATHS)
            or (profile_role == "student" and request.url.path in LOCAL_STUDENT_PREFER_LOCAL_FALLBACK_PATHS)
        )
        record_has_unsuccessful_payload = (
            teacher_fallback_path or student_fallback_path
        ) and _record_has_unsuccessful_json_payload(record)
        if prefer_local_fallback or record is None or record["status"] >= 400 or record_has_unsuccessful_payload:
            local_record = _build_local_api_fallback(store, request, request_body)
            if local_record is not None:
                record = local_record

        if record is None and allow_live_proxy:
            record = await _proxy_and_cache(
                store,
                request,
                live_url,
                profile_name or profile_role or "public",
                request_body=request_body,
            )

        if record is None:
            return JSONResponse(
                {
                    "success": False,
                    "error": {
                        "code": "MirrorMiss",
                        "message": f"No mirrored response for {request.method} {request.url.path}",
                    },
                },
                status_code=404,
            )

        body = _maybe_rewrite_body(record["body"], record["content_type"], record["headers"])
        if "json" in record["content_type"].lower():
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                payload = None
            if isinstance(payload, dict):
                payload = _postprocess_json_payload(store, request, payload)
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        body = _normalize_success_json(body, record["content_type"])
        headers = _sanitize_outbound_headers(record["headers"])
        return Response(content=body, status_code=record["status"], media_type=record["content_type"], headers=headers)

    @app.get("/external/{host}/{asset_path:path}")
    @app.get("/_external/{host}/{asset_path:path}")
    def external_asset(host: str, asset_path: str, request: Request) -> Response:
        live_url = _build_live_url(host, f"/{asset_path}", request.url.query)
        archived_course_asset = lookup_course_archive_asset(store, live_url)
        if archived_course_asset is not None:
            archived_local_path = str(archived_course_asset.get("local_path") or "").strip()
            if archived_course_asset.get("present") and archived_local_path:
                archived_local_file = store.root / archived_local_path
                if archived_local_file.is_file():
                    response = _static_response_or_404(archived_local_file, expected_asset_path=asset_path)
                    if response.status_code != 404:
                        return response
            return build_course_asset_not_local_response(archived_course_asset, live_url)

        for path in _local_asset_candidates(store, host, asset_path):
            if path.is_file():
                response = _static_response_or_404(path, expected_asset_path=asset_path)
                if response.status_code != 404:
                    return response

        if allow_live_proxy:
            proxied = _proxy_and_cache_asset(store, live_url)
            if proxied is not None:
                return proxied

        synthetic = _synthetic_asset_response(host, asset_path)
        if synthetic is not None:
            return synthetic

        missing_fallback = _synthetic_missing_asset_response(host, asset_path)
        if missing_fallback is not None:
            return missing_fallback

        return Response(status_code=404)

    @app.get("/login")
    @app.get("/background/login")
    def login_page() -> Response:
        return _serve_login_response()

    @app.get("/logout")
    def logout_page(request: Request) -> Response:
        return _serve_logout_response(request)

    @app.post("/logout")
    def logout_page_post(request: Request) -> Response:
        return _serve_logout_response(request)

    @app.get("/{requested_path:path}")
    def frontend_asset(requested_path: str, request: Request) -> Response:
        if requested_path == "":
            resolved_profile = _resolve_profile(store, request)
            profile_name = resolved_profile["profile_name"] if resolved_profile else _resolve_profile_name(store, request)
            target = _default_frontend_route_for_role(_profile_role(profile_name, resolved_profile))
            return RedirectResponse(url=target or "/login")

        route_key = f"/{requested_path.strip('/')}" if requested_path else "/"

        normalized_redirect_target = _normalized_frontend_redirect_target(store, request)
        if normalized_redirect_target:
            return RedirectResponse(url=normalized_redirect_target, status_code=307)

        non_core_redirect_target = _non_core_frontend_redirect_target(store, request, route_key)
        if non_core_redirect_target:
            return RedirectResponse(url=non_core_redirect_target, status_code=307)

        normalized = requested_path or "index.html"
        if route_key == "/competitionCenter/questionBank":
            tab_component = (request.query_params.get("tabComponent") or "").strip()
            if tab_component == "campusQuestionBank":
                return RedirectResponse(url="/competitionCenter/questionBankCenter/campus", status_code=307)
            return RedirectResponse(url="/competitionCenter/questionBankCenter/platform", status_code=307)
        if _is_benign_placeholder_route(normalized):
            return _benign_placeholder_response()

        protected_redirect_target = _protected_frontend_redirect_target(store, request, route_key)
        if protected_redirect_target:
            return RedirectResponse(url=protected_redirect_target, status_code=303)

        for candidate in _local_asset_candidates(store, "steam.fun", normalized):
            if candidate.is_file():
                response = _static_response_or_404(candidate, expected_asset_path=normalized)
                if response.status_code != 404:
                    return response

        if _looks_like_asset_path(normalized):
            if allow_live_proxy:
                live_url = _build_live_url("steam.fun", request.url.path, request.url.query)
                proxied = _proxy_and_cache_asset(store, live_url)
                if proxied is not None:
                    return proxied
            synthetic = _synthetic_asset_response("steam.fun", normalized)
            if synthetic is not None:
                return synthetic
            missing_fallback = _synthetic_missing_asset_response("steam.fun", normalized)
            if missing_fallback is not None:
                return missing_fallback
            return Response(status_code=404)

        preferred_profile = _preferred_profile_for_request(store, request, route_key)
        bootstrap_script = _build_route_bootstrap(store, preferred_profile, request, route_key)

        def finalize_frontend_response(response: Response) -> Response:
            if _is_login_route(route_key):
                response.delete_cookie("mirror_profile", path="/")
                response.headers["cache-control"] = "no-store, no-cache, must-revalidate, max-age=0"
                response.headers["pragma"] = "no-cache"
                response.headers["expires"] = "0"
            return response

        for candidate_route in _profile_specific_route_aliases(route_key, preferred_profile):
            captured_route = store.lookup_route_capture(
                candidate_route,
                preferred_profile=preferred_profile,
            )
            if captured_route is None:
                continue
            if _is_login_redirect_capture(captured_route["final_url"]):
                continue
            captured_path = store.root / captured_route["html_path"]
            freeze_scripts = captured_route["profile_name"] == "student" and candidate_route.startswith("/code-classroom")
            return finalize_frontend_response(
                _captured_route_response(
                    captured_path,
                    store=store,
                    prune_missing_asset_hints=not allow_live_proxy,
                    freeze_scripts=freeze_scripts,
                    route_key=route_key,
                    teacher_session_bootstrap=bootstrap_script,
                )
            )

        if _is_login_route(route_key):
            if route_key == "/background/login" and store.get_profile("admin") is not None:
                return finalize_frontend_response(
                    Response(
                        content=_render_local_admin_login_page(request).encode("utf-8"),
                        media_type="text/html",
                    )
                )
            login_capture = _lookup_login_route_capture(
                store,
                route_key,
                preferred_profile=preferred_profile or _preferred_profile_for_route(route_key),
            )
            if login_capture is not None:
                login_capture_path = store.root / login_capture["html_path"]
                return finalize_frontend_response(
                    _captured_route_response(
                        login_capture_path,
                        store=store,
                        prune_missing_asset_hints=not allow_live_proxy,
                        freeze_scripts=False,
                        route_key=route_key,
                        teacher_session_bootstrap=bootstrap_script,
                    )
                )

        # Unknown route-like paths fall back to the SPA shell.
        shell_path = store.root / "origin" / "steam.fun" / "index.html"
        if bootstrap_script:
            return finalize_frontend_response(
                _captured_route_response(
                    shell_path,
                    store=store,
                    prune_missing_asset_hints=not allow_live_proxy,
                    freeze_scripts=False,
                    route_key=route_key,
                    teacher_session_bootstrap=bootstrap_script,
                )
            )
        return finalize_frontend_response(
            _captured_route_response(
                shell_path,
                store=store,
                prune_missing_asset_hints=not allow_live_proxy,
                freeze_scripts=False,
                route_key=route_key,
                teacher_session_bootstrap=None,
            )
        )

    return app


def _local_login_response(store: MirrorStore, payload: dict[str, Any], *, expected_login_path: str) -> Response:
    username = (
        payload.get("userName")
        or payload.get("username")
        or payload.get("account")
        or payload.get("phone")
    )
    submitted_password = str(payload.get("password") or "")
    profile = store.get_profile_by_username(username)

    if expected_login_path == STUDENT_LOGIN_PATH:
        canonical_student_profile = store.get_profile("student")
        if (
            canonical_student_profile is not None
            and canonical_student_profile.get("login_path") == STUDENT_LOGIN_PATH
            and str(canonical_student_profile.get("username") or "").strip() == str(username or "").strip()
        ):
            profile = canonical_student_profile

    # Fallback: if no profile row exists for this username but a local_students
    # row matches (e.g. student created via /java-api/school/stu/create after
    # the seeded profiles snapshot), auto-provision a profile on the fly so the
    # student can sign in immediately.
    if expected_login_path == STUDENT_LOGIN_PATH:
        student_row = store.find_local_student_by_username(username or "")
        existing_profile_name = str((profile or {}).get("profile_name") or "").strip()
        has_canonical_student_profile = (
            profile is not None
            and profile.get("login_path") == STUDENT_LOGIN_PATH
            and not existing_profile_name.startswith("local_student_")
        )
        if student_row is not None and not has_canonical_student_profile:
            local_profile_name = f"local_student_{int(student_row.get('id') or 0)}"
            existing_local_profile = store.get_profile(local_profile_name) or profile
            password_hash = str((existing_local_profile or {}).get("password_hash") or "").strip()
            if not password_hash:
                password_hash = _hash_login_password(submitted_password) if submitted_password else _hash_login_password("123456")
            token = str((existing_local_profile or {}).get("token") or "").strip() or _mint_local_login_token(store, prefix="local-student")
            profile = store.upsert_student_login_profile(
                student_row,
                password_hash=password_hash,
                token=token,
                login_path=STUDENT_LOGIN_PATH,
            )

    profile_password_hash = str((profile or {}).get("password_hash") or "")
    submitted_password_hash = submitted_password if submitted_password == profile_password_hash else _hash_login_password(submitted_password)
    profile_name = str((profile or {}).get("profile_name") or "")
    allow_default_local_student_password = (
        expected_login_path == STUDENT_LOGIN_PATH
        and profile_name.startswith("local_student_")
        and _is_default_local_password(submitted_password)
    )

    if (
        not profile
        or profile["login_path"] != expected_login_path
        or (
            submitted_password_hash != profile_password_hash
            and not allow_default_local_student_password
        )
    ):
        return JSONResponse(
            {
                "success": False,
                "error": {"code": "AuthFailure", "message": "Invalid username or password"},
            },
            status_code=200,
        )

    if expected_login_path == TEACHER_LOGIN_PATH and _profile_is_disabled(profile):
        return JSONResponse(
            {
                "success": False,
                "error": {"code": "AccountDisabled", "message": "该账号已停用，请联系机构管理员"},
            },
            status_code=200,
        )

    profile_role = _profile_role(profile["profile_name"], profile)
    response_content = profile["login_content"]
    if _is_teacher_like_role(profile_role) and isinstance(response_content, dict):
        response_content = _json_deep_copy(response_content)
        response_content["authTree"] = json.dumps(
            _permission_tree_as_auth_tree(_teacher_permission_tree(store, profile["profile_name"])),
            ensure_ascii=False,
        )
    response = JSONResponse(
        {
            "success": True,
            "content": response_content,
            "mirror": {
                "profile": profile["profile_name"],
                "role": profile_role,
                "redirect": _default_frontend_route_for_role(profile_role),
            },
            "error": {"message": "", "code": ""},
        },
        status_code=200,
    )
    response.set_cookie(
        "mirror_profile",
        profile["profile_name"],
        path="/",
        max_age=8 * 60 * 60,
        httponly=True,
        samesite="lax",
    )
    return response


def _is_default_local_password(submitted_password: str) -> bool:
    """True when submitted password is the local-mirror default 123456."""
    return str(submitted_password or "").strip() == "123456"


def _mint_local_login_token(store: MirrorStore, *, prefix: str) -> str:
    """Generate a JWT-shaped opaque token so frontend treats it as a normal session token."""
    import uuid as _uuid
    import time as _time
    code = f"{_uuid.uuid4()}"
    issued_at = int(_time.time())
    payload = {
        "code": code,
        "loginTime": issued_at,
        "isStu": True,
        "exp": issued_at + 60 * 60 * 24 * 365,
        "iat": issued_at,
    }
    secret = "local-mirror-default-secret"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    body_b64 = base64.urlsafe_b64encode(body).decode("ascii").rstrip("=")
    digest = hashlib.sha256((secret + "." + body_b64).encode("utf-8")).digest()
    sig_b64 = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{prefix}.{body_b64}.{sig_b64}"


def _resolve_authenticated_profile(store: MirrorStore, request: Request) -> dict[str, Any] | None:
    token = _normalize_auth_token(request.headers.get("authorization"))
    profile = store.get_profile_by_token(token)
    if profile is not None:
        return profile

    explicit_profile_name = (request.headers.get("x-mirror-profile") or "").strip()
    if explicit_profile_name:
        profile = store.get_profile(explicit_profile_name)
        if profile is not None:
            return profile

    cookie_profile_name = (request.cookies.get("mirror_profile") or "").strip()
    if cookie_profile_name:
        profile = store.get_profile(cookie_profile_name)
        if profile is not None:
            return profile
    return None


def _resolve_profile(store: MirrorStore, request: Request) -> dict[str, Any] | None:
    profile = _resolve_authenticated_profile(store, request)
    if profile is not None:
        return profile
    inferred_profile_name = _infer_profile_from_request(request)
    if inferred_profile_name:
        return store.get_profile(inferred_profile_name)
    return None


def _resolve_profile_name(store: MirrorStore, request: Request) -> str | None:
    profile = _resolve_profile(store, request)
    if profile:
        return profile["profile_name"]
    return _infer_profile_from_request(request)


def _student_user_info_from_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(profile, dict):
        return {}

    fresh_auth = profile.get("fresh_auth") if isinstance(profile.get("fresh_auth"), dict) else {}
    fresh_auth_user = fresh_auth.get("userInfo") if isinstance(fresh_auth.get("userInfo"), dict) else {}
    stu_user = fresh_auth_user.get("stuUserInfo") if isinstance(fresh_auth_user.get("stuUserInfo"), dict) else {}
    if stu_user:
        return _json_deep_copy(stu_user)

    login_content = profile.get("login_content")
    if isinstance(login_content, dict):
        login_user = login_content.get("userInfo") if isinstance(login_content.get("userInfo"), dict) else {}
        if login_user:
            return _json_deep_copy(login_user)
        login_stu = login_content.get("stuUserInfo") if isinstance(login_content.get("stuUserInfo"), dict) else {}
        if login_stu:
            return _json_deep_copy(login_stu)

    vuex_state = profile.get("vuex_state") if isinstance(profile.get("vuex_state"), dict) else {}
    vuex_user = vuex_state.get("user") if isinstance(vuex_state.get("user"), dict) else {}
    vuex_user_info = vuex_user.get("userInfo") if isinstance(vuex_user.get("userInfo"), dict) else {}
    vuex_stu = vuex_user_info.get("stuUserInfo") if isinstance(vuex_user_info.get("stuUserInfo"), dict) else {}
    if vuex_stu:
        return _json_deep_copy(vuex_stu)
    direct_stu = vuex_user.get("stuUserInfo") if isinstance(vuex_user.get("stuUserInfo"), dict) else {}
    if direct_stu:
        return _json_deep_copy(direct_stu)
    return {}


def _local_fresh_auth_response(store: MirrorStore, request: Request) -> Response:
    path = request.url.path or ""
    profile = _resolve_profile(store, request)
    if profile is None:
        profile_name = _resolve_profile_name(store, request) or "teacher"
        profile = store.get_profile(profile_name) or store.get_profile("teacher")
    login_content = (profile or {}).get("login_content") or {}
    fresh_auth = (profile or {}).get("fresh_auth") or {}
    if path == "/java-api/student/stu/freshData":
        # Build the student freshData payload from the profile data.
        homepage_content = _build_homepage_content(store, request)
        stu_user = _student_user_info_from_profile(profile)
        stu_base_info = stu_user.get("stuUserInfo") if isinstance(stu_user.get("stuUserInfo"), dict) else {}
        school_info = _merge_dict_defaults(
            (fresh_auth.get("schoolInfo") if isinstance(fresh_auth, dict) else None) or {},
            homepage_content.get("schoolInfo") if isinstance(homepage_content.get("schoolInfo"), dict) else {},
        )
        role_list = (fresh_auth.get("roleList") if isinstance(fresh_auth, dict) else None) or []
        content = {
            "identity": 2,
            "userInfo": {
                "stuUserInfo": stu_user,
                "pauth": stu_user.get("pauth", True) if isinstance(stu_user, dict) else True,
            },
            "stuUserInfo": stu_user,
            "stuBaseInfo": stu_base_info,
            "schoolInfo": school_info,
            "homepageData": _json_deep_copy(homepage_content.get("homepageData") or {}),
            "homepage": _json_deep_copy(homepage_content.get("homepage") or {}),
            "imgUrl": homepage_content.get("imgUrl"),
            "roleList": role_list,
        }
        return JSONResponse({"success": True, "content": content, "error": {"message": "", "code": ""}}, status_code=200)
    if path == "/java-api/school/tch/freshData":
        homepage_content = _build_homepage_content(store, request)
        fresh_auth_user = fresh_auth.get("userInfo") if isinstance(fresh_auth.get("userInfo"), dict) else {}
        tch_user = (
            fresh_auth_user
            or login_content.get("userInfo")
            or login_content.get("tchUserInfo")
            or {}
        )
        school_info = _merge_dict_defaults(
            (fresh_auth.get("schoolInfo") if isinstance(fresh_auth, dict) else None) or {},
            homepage_content.get("schoolInfo") if isinstance(homepage_content.get("schoolInfo"), dict) else {},
        )
        role_list = (fresh_auth.get("roleList") if isinstance(fresh_auth, dict) else None) or [1, 2]
        content = {
            "identity": 1,
            "userInfo": tch_user,
            "schoolInfo": school_info,
            "homepageData": _json_deep_copy(homepage_content.get("homepageData") or {}),
            "homepage": _json_deep_copy(homepage_content.get("homepage") or {}),
            "imgUrl": homepage_content.get("imgUrl"),
            "roleList": role_list,
        }
        return JSONResponse({"success": True, "content": content, "error": {"message": "", "code": ""}}, status_code=200)
    # Default: legacy auth tree endpoint used by SPA bootstrap.
    message = None
    profile_role = _profile_role((profile or {}).get("profile_name"), profile)
    if _is_teacher_like_role(profile_role):
        profile_name = str((profile or {}).get("profile_name") or "teacher")
        message = json.dumps(
            _permission_tree_as_auth_tree(_teacher_permission_tree(store, profile_name)),
            ensure_ascii=False,
        )
    elif isinstance(login_content, dict):
        message = login_content.get("authTree")
    auth_payload = {"flag": True, "message": message}
    stu_info = _student_user_info_from_profile(profile)
    if isinstance(stu_info, dict) and stu_info.get("id"):
        auth_payload["userInfo"] = {"stuUserInfo": stu_info}
    if isinstance(login_content, dict):
        tch_info = login_content.get("userInfo")
        if not auth_payload.get("userInfo") and isinstance(tch_info, dict) and tch_info.get("id"):
            auth_payload["userInfo"] = tch_info
    return JSONResponse({
        "success": True,
        "content": auth_payload,
        "error": {"message": "", "code": ""},
    }, status_code=200)
async def _proxy_and_cache(
    store: MirrorStore,
    request: Request,
    live_url: str,
    profile_name: str,
    request_body: bytes,
) -> dict[str, Any] | None:
    headers = dict(request.headers)
    headers.pop("host", None)
    profile = store.get_profile(profile_name)
    if profile and "authorization" not in {key.lower() for key in headers}:
        headers["Authorization"] = profile["token"]

    response = requests.request(
        method=request.method,
        url=live_url,
        headers=headers,
        data=request_body or None,
        timeout=60,
    )
    stored_path = store.store_api_response(
        profile_name,
        method=request.method,
        url=live_url,
        status=response.status_code,
        headers=dict(response.headers),
        body=response.content,
        request_body=request_body,
    )
    return store.lookup_api_response(
        profile_name,
        method=request.method,
        url=live_url,
        request_body=request_body,
    )


def _proxy_and_cache_asset(store: MirrorStore, live_url: str) -> Response | None:
    response = _fetch_static_asset(live_url)
    if response is None:
        return None

    with response:
        headers = dict(response.headers)
        content_type = headers.get("content-type") or mimetypes.guess_type(urlparse(live_url).path)[0] or "application/octet-stream"
        host = urlparse(live_url).netloc
        is_textual = _is_textual_content_type(content_type)
        content_length_header = (headers.get("content-length") or "").strip()
        inline_ok = True
        if content_length_header.isdigit():
            inline_ok = int(content_length_header) <= INLINE_REWRITE_MAX_BYTES
        collected = bytearray() if is_textual and inline_ok else None

        def chunk_iter():
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if not chunk:
                    continue
                if collected is not None:
                    collected.extend(chunk)
                yield chunk

        if is_same_origin_host(host):
            store.store_origin_asset_stream(live_url, chunk_iter(), status=response.status_code, headers=headers)
        else:
            store.store_external_asset_stream(live_url, chunk_iter(), status=response.status_code, headers=headers)

    if is_textual and collected is not None:
        body = _maybe_rewrite_body(bytes(collected or b""), content_type, headers)
        return Response(content=body, status_code=response.status_code, headers={"content-type": content_type})
    indexed_asset = store.lookup_asset(live_url)
    if indexed_asset is None:
        return None
    return FileResponse(store.root / indexed_asset["local_path"], media_type=content_type, status_code=response.status_code)


def _static_response_or_404(path: Path, *, expected_asset_path: str | None = None) -> Response:
    if not path.is_file():
        return Response(status_code=404)
    if _is_mislabeled_html_asset(path, expected_asset_path):
        return Response(status_code=404)

    guessed_type, _ = mimetypes.guess_type(path.name)
    media_type = guessed_type or "application/octet-stream"
    try:
        size = path.stat().st_size
    except OSError:
        size = INLINE_REWRITE_MAX_BYTES + 1

    body: bytes | None = None
    if guessed_type is None and size <= INLINE_REWRITE_MAX_BYTES:
        body = path.read_bytes()
        sniffed_media_type = _sniff_local_media_type(path, body)
        if sniffed_media_type:
            media_type = sniffed_media_type

    if not _is_textual_content_type(media_type):
        return FileResponse(path, media_type=media_type)
    if size > INLINE_REWRITE_MAX_BYTES:
        return FileResponse(path, media_type=media_type)
    if body is None:
        body = path.read_bytes()
    body = _maybe_rewrite_body(body, media_type)
    return Response(content=body, media_type=media_type)


def _public_html_response(path: Path) -> Response:
    if not path.is_file():
        return Response(status_code=404)
    response = Response(content=path.read_bytes(), media_type="text/html")
    return _no_store_response(response)


def _no_store_response(response: Response) -> Response:
    if response.status_code != 404:
        response.headers["cache-control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["pragma"] = "no-cache"
        response.headers["expires"] = "0"
    return response


def _inject_back_to_home_button(text: str) -> str:
    """Brand the captured login page without changing its login behavior."""
    snippet = (
        '<style>'
        'html,body,#app,.login-container{background:transparent!important;}body{position:relative;}'
        'body:before{content:"";position:fixed;inset:0;z-index:-2;background:linear-gradient(115deg,rgba(2,8,28,.9),rgba(2,8,28,.38)),url("/_site/homepage/media/contact-bg.webp") center/cover no-repeat!important;}'
        'body:after{content:"";position:fixed;inset:0;z-index:-1;background:radial-gradient(circle at 75% 20%,rgba(111,255,0,.2),transparent 34%);pointer-events:none}'
        '.lq-login-brand{position:fixed;right:4vw;top:50%;z-index:9998;width:min(28vw,320px);transform:translateY(-50%);filter:drop-shadow(0 22px 45px rgba(0,0,0,.48));}'
        '.lq-login-video{position:fixed;inset:0;z-index:-3;width:100%;height:100%;object-fit:cover;opacity:.58}'
        '.lq-back-home{position:fixed;top:1.2rem;left:1.2rem;z-index:9999;display:inline-flex;align-items:center;gap:.5rem;padding:.55rem 1rem;border-radius:999px;background:rgba(2,8,28,.72);color:#fff;font-family:"Noto Sans SC",sans-serif;font-weight:600;font-size:.85rem;text-decoration:none;border:1px solid rgba(255,255,255,.25);backdrop-filter:blur(12px)}'
        '.lq-back-home:hover{background:#6fff00;color:#010828}'
        '@media(max-width:900px){.lq-login-brand{display:none}}'
        '</style>'
        '<video class="lq-login-video" autoplay loop muted playsinline><source src="/_site/homepage/media/signal-cloudfront-20260331-055729.mp4" type="video/mp4"></video>'
        '<img class="lq-login-brand" src="/_site/homepage/media/brand-logo.png" alt="乐启享">'
        '<a class="lq-back-home" href="/" aria-label="返回官网首页"><span>← 返回官网首页</span></a>'
    )
    if "</body>" in text:
        return text.replace("</body>", snippet + "</body>", 1)
    return text + snippet

def _captured_route_response(
    path: Path,
    *,
    route_key: str | None = None,
    store: MirrorStore | None = None,
    prune_missing_asset_hints: bool = False,
    freeze_scripts: bool,
    teacher_session_bootstrap: str | None = None,
) -> Response:
    if not path.is_file():
        return Response(status_code=404)
    text = path.read_text(encoding="utf-8", errors="ignore")
    text = rewrite_external_urls(text)
    if prune_missing_asset_hints and store is not None:
        text = _prune_missing_frontend_asset_hints(store, text)
    if freeze_scripts:
        text = SCRIPT_TAG_RE.sub("", text)
        text = _sanitize_frozen_classroom_snapshot(text)
    text = _inject_teacher_session_bootstrap(text, teacher_session_bootstrap)
    text = _inject_runtime_guards(text)
    if route_key and route_key in {"/login", "/background/login"}:
        text = _inject_back_to_home_button(text)
    return Response(content=text.encode("utf-8"), media_type="text/html")


def _serve_login_response() -> Response:
    response = Response(content=LOGIN_HTML_PATH.read_bytes(), media_type="text/html")
    response.delete_cookie("mirror_profile", path="/")
    response.headers["cache-control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["pragma"] = "no-cache"
    response.headers["expires"] = "0"
    return response


_LOGOUT_HTML_TEMPLATE = (
    """<!doctype html>
    <html lang="zh-CN">
    <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>\u5df2\u9000\u51fa \u00b7 \u4e50\u542f\u4eab</title>
    <style>
    html,body{height:100%;margin:0;background:#07132d;color:#eef4ff;font-family:"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
    .wrap{display:grid;place-items:center;height:100%;text-align:center;padding:24px}
    .wrap h1{margin:0 0 10px;font-size:22px;letter-spacing:.06em}
    .wrap p{margin:0;color:rgba(238,244,255,.6);font-size:14px}
    </style>
    </head>
    <body>
    <div class="wrap">
      <h1>\u5df2\u5b89\u5168\u9000\u51fa</h1>
      <p>\u6b63\u5728\u8df3\u8f6c\u767b\u5f55\u9875\u2026</p>
    </div>
    <script>
    (function(){
    var KEYS=["mirror_profile","schoolInfo","homepage","Classroom","teacherPlanList","subject_id","courseArranging","updatePhoneStorage","updatePasswordStorage","updateNoticeStorage","hasShownDialogStorage","login_redirect"];
    for(var i=0;i<KEYS.length;i++){try{sessionStorage.removeItem(KEYS[i]);}catch(e){}}
    try{localStorage.removeItem("vuex");}catch(e){}
    try{document.cookie="mirror_profile=; Max-Age=0; path=/; SameSite=Lax";}catch(e){}
    var qs=location.search||"";
    var m=qs.match(/[?&](?:next|redirect|redirect_url|target)=([^&]+)/);
    var target="/login";
    if(m){try{target=decodeURIComponent(m[1]);}catch(e){}}
    if(!target||target.charAt(0)!=="/"||target.indexOf("//")===0){target="/login";}
    setTimeout(function(){window.location.replace(target);},120);
    })();
    </script>
    </body>
    </html>
    """
)


def _serve_logout_response(request: Request) -> Response:
    """Wrap the logout page: clears cookie, no-store, wipes storage client-side."""
    response = Response(content=_LOGOUT_HTML_TEMPLATE.encode("utf-8"), media_type="text/html")
    response.delete_cookie("mirror_profile", path="/")
    response.headers["cache-control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["pragma"] = "no-cache"
    response.headers["expires"] = "0"
    return response
