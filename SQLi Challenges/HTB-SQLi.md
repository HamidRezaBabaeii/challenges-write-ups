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
    ``` |'-"            | \'' - \"" ,  | 
        |' OR 1=1 -- -  | ' OR '1'='1  |
        |" OR 1=1 -- -  | " OR "1"="1  |
        |') OR 1=1 -- - | ') OR '1'='1 |
        |") OR 1=1 -- - | ") OR "1"="1 |
