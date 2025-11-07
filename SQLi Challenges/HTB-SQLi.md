# CTF - Hack The Box - Module 33 Section 518 - First Challenge
## Challenge : What is the password hash for the user 'admin'?
What should we do? At first time we should check every input section in web-app to find SQLi, then use it to retrieve admin password.

## First Step
- Find pages and them input sections.
    - We have two page
        - ***Login page***
        - ***Create Account***

<p align="center">
    <img src="../static/image/SQLi-img/HTB-33-518-LOGIN.png" >
    We have two input boxes and we will test our injections on them.
</p>

<hr>

<p align="center">
    <img src="../static/image/SQLi-img/HTB-33-518-CACCOUNT.png" >
    We have four input boxes and we will test our injections on them.
</p>

<hr>

## Second Step
- Prepare tools and payloads
    - Run Burp
    - Write usefull and different payloads for injection

| Payload | DEFINE |
| --- | --- |
| `' OR '1'='1` | Basic string-based SQLi |
| `" OR "1"="1` | Double-quote variant |
| `' OR 1=1 -- -` | No quotes + comment (numeric/boolean test) |
| `" OR 1=1 -- -` | Double-quote no-quotes variant |
| `') OR '1'='1` | Close paren + string injection |
| `") OR "1"="1` | Close paren double-quote |
| `' "` | mixed quotes/edge-case (test escaping) |
| `\' OR \'1\'=\'1` | escaped single-quotes (in forms that escape differently) |

<hr>

### Get start to find vulnerable Page and input box
<p align="center">
    <img src="../static/image/SQLi-img/HTB-33-518-LOGIN-test.png" alt="test SQLi">  
</p>

**Fist we check login page, I'll use ' or " to see has vulnerable box or not! I tested payloads on login page but happend nothing I went on second page,If you focuse on response, you'll got our request redirected to login.php.So we can understand all inpusts sanitization in this page and we have not error.**