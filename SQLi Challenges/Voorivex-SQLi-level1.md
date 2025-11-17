# SQLi Level 1 (String UNION)- Voorivex Academy

## Summary

-  **Requirements:**
    - **Programming Language: PHP**

    - **Skill: Source Code Auditing**

    - **SQLi: UNION technique in string values**

  
- **Objective**

    - **Your goal is to extract the flag from the database by exploiting a SQL injection vulnerability**

**<p> As mentioned, we're looking for vulnerable queries in the web app — let's get started! :)</p>**

<hr>

**First thing that you see when opening the site and it attracts your attention is this -> ***URL: XYZ.online/post.php?id=1*****
**So first I try write "'" end of url query after that I'll see this error:**

<img src="../static/image/SQLi-img/voorivex-academy-sqli1-1.png" alt="error page">

**Actualy "'" works and we have vulnerable in this url.**
**We broke the SQL query now we need to fix it. let's try ***URL: XYZ.online/post.php?id=1'+--+-***, its worked:**

<img src="../static/image/SQLi-img/voorivex-academy-sqli1-2.png" alt="returned 200 ok">