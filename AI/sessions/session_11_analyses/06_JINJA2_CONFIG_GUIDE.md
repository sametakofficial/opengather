# ARCHIVERR CONFIG JINJA2 KULLANIM KILAVUZU

```yaml
tarih: 2025-12-04
referans: FlexGet Jinja2 documentation
```

---

## 1. TEMEL SYNTAX

### 1.1 Değişken Yazdırma

```jinja2
{{ değişken }}
{{ job.input.value }}
{{ config.tmdb.api_key }}
```

### 1.2 Yorum

```jinja2
{# Bu bir yorum - render edilmez #}
```

### 1.3 Tag'ler (Logic)

```jinja2
{% tag %}
{% if koşul %}...{% endif %}
{% for item in liste %}...{% endfor %}
{% set değişken = değer %}
```

---

## 2. DEĞİŞKEN TANIMLAMA (SET)

```jinja2
{# Basit değişken #}
{% set m = job.plugins.tmdb.movie %}

{# Çoklu satır #}
{% set template %}
  {{ m.title }} ({{ m.release_date[:4] }})
{% endset %}

{# Hesaplama ile #}
{% set year = m.release_date[:4] | int %}
{% set next_year = year + 1 %}

{# Kullanım #}
{{ m.title }}
```

---

## 3. KOŞULLAR (IF/ELIF/ELSE)

### 3.1 Basit If

```jinja2
{% if job.plugins.renamer.parsed.movie %}
  Bu bir film
{% endif %}
```

### 3.2 If/Else

```jinja2
{% if job.plugins.renamer.parsed.movie %}
  Film: {{ job.plugins.tmdb.movie.title }}
{% else %}
  Film değil
{% endif %}
```

### 3.3 If/Elif/Else

```jinja2
{% if job.plugins.renamer.parsed.movie %}
  /movies/{{ m.title }}/
{% elif job.plugins.renamer.parsed.show %}
  /shows/{{ s.name }}/Season {{ s.season }}/
{% else %}
  /unknown/{{ job.input.data.filename }}
{% endif %}
```

### 3.4 Tek Satır If (Ternary)

```jinja2
{{ "Film" if parsed.movie else "Dizi" }}
{{ m.title if m else "Bilinmeyen" }}
```

### 3.5 Koşul Operatörleri

```jinja2
{# Karşılaştırma #}
{% if year > 2020 %}
{% if rating >= 7.0 %}
{% if codec == 'hevc' %}
{% if title != 'Unknown' %}

{# Mantıksal #}
{% if movie and year > 2020 %}
{% if movie or show %}
{% if not movie %}

{# Üyelik #}
{% if 'Action' in genres %}
{% if codec in ['hevc', 'h264'] %}

{# Boş kontrol #}
{% if movie %}              {# None/empty değilse #}
{% if movie is defined %}   {# Tanımlı mı #}
{% if movie is none %}      {# None mı #}
```

---

## 4. DÖNGÜLER (FOR)

### 4.1 Basit Döngü

```jinja2
{% for genre in job.plugins.tmdb.movie.genres %}
  {{ genre }}
{% endfor %}
```

### 4.2 Loop Değişkenleri

```jinja2
{% for audio in job.plugins.ffprobe.audio %}
  {{ loop.index }}      {# 1'den başlar #}
  {{ loop.index0 }}     {# 0'dan başlar #}
  {{ loop.first }}      {# İlk eleman mı #}
  {{ loop.last }}       {# Son eleman mı #}
  {{ loop.length }}     {# Toplam eleman sayısı #}
{% endfor %}
```

### 4.3 Döngü ile Koşul

```jinja2
{% for sub in job.plugins.ffprobe.subtitles if sub.language == 'eng' %}
  English subtitle: {{ sub.codec }}
{% endfor %}
```

### 4.4 Boş Döngü Kontrolü

```jinja2
{% for audio in audios %}
  {{ audio.language }}
{% else %}
  Ses yok
{% endfor %}
```

---

## 5. FİLTRELER

### 5.1 Metin Filtreleri

```jinja2
{{ title | upper }}              {# BÜYÜK HARF #}
{{ title | lower }}              {# küçük harf #}
{{ title | capitalize }}         {# İlk harf büyük #}
{{ title | title }}              {# Her Kelime Büyük #}
{{ title | trim }}               {# Boşlukları kırp #}
{{ title | replace(' ', '_') }} {# Değiştir #}
{{ title | truncate(20) }}       {# 20 karaktere kırp #}
```

### 5.2 Sayı Filtreleri

```jinja2
{{ rating | round }}             {# Yuvarla #}
{{ rating | round(1) }}          {# 1 ondalık #}
{{ value | int }}                {# Integer'a çevir #}
{{ value | float }}              {# Float'a çevir #}
{{ value | abs }}                {# Mutlak değer #}
{{ bytes | filesizeformat }}     {# 5.4 GB gibi #}
```

### 5.3 Liste Filtreleri

```jinja2
{{ genres | join(', ') }}        {# Liste → string #}
{{ genres | first }}             {# İlk eleman #}
{{ genres | last }}              {# Son eleman #}
{{ genres | length }}            {# Eleman sayısı #}
{{ genres | sort }}              {# Sırala #}
{{ genres | reverse }}           {# Ters çevir #}
{{ genres | unique }}            {# Tekrarsız #}
{{ genres | random }}            {# Rastgele seç #}
```

### 5.4 Default Değer

```jinja2
{{ title | default('Bilinmeyen') }}
{{ rating | default(0) }}
{{ items | default([]) }}
```

### 5.5 Zincirleme Filtreler

```jinja2
{{ title | lower | replace(' ', '_') | truncate(50) }}
```

---

## 6. ARCHIVERR ÖZEL KULLANIM

### 6.1 Sistem Alias'ları

```jinja2
{# 8 sistem alias'ı #}
{{ run.id }}                     {# Run ID #}
{{ job.input.value }}            {# Dosya yolu #}
{{ job.output.values }}          {# Çıktı dosyaları #}
{{ jobs | length }}              {# Toplam job sayısı #}
{{ plugins.tmdb.movie }}         {# Plugin verisi #}
{{ config.archive_path }}        {# Config değeri #}
{{ options.debug }}              {# Options değeri #}
{{ provides }}                   {# Provides registry #}
{{ events }}                     {# Event bus #}
```

### 6.2 Kullanıcı Alias'ları

```yaml
# config.yml
aliases:
  m: job.plugins.tmdb.movie
  s: job.plugins.tmdb.show
  p: job.plugins.renamer.parsed
```

```jinja2
{# Kullanım #}
{{ m.title }}
{{ p.movie.year }}
{{ s.season }}
```

### 6.3 Inline Alias (En Esnek)

```jinja2
{% set m = job.plugins.tmdb.movie %}
{% set year = m.release_date[:4] %}
{% set quality = job.plugins.ffprobe.video.height ~ 'p' %}

{{ m.title }} ({{ year }}) [{{ quality }}]
```

---

## 7. ÖRNEK CONFIG SENARYOLARI

### 7.1 Film Kaydetme

```yaml
tasker:
  tasks:
    - name: save_movie
      type: save
      condition: "{{ job.plugins.renamer.parsed.movie }}"
      template: |
        {% set m = job.plugins.tmdb.movie %}
        {% set year = m.release_date[:4] %}
        {% set ext = job.input.data.extension %}
        {{ config.archive_path }}/Movies/
        {{ m.title }} ({{ year }})/
        {{ m.title }}.{{ ext }}
```

### 7.2 Dizi Kaydetme

```yaml
tasker:
  tasks:
    - name: save_show
      type: save
      condition: "{{ job.plugins.renamer.parsed.show }}"
      template: |
        {% set s = job.plugins.tmdb.show %}
        {% set p = job.plugins.renamer.parsed.show %}
        {{ config.archive_path }}/Shows/
        {{ s.name }}/
        Season {{ '%02d' % p.season }}/
        {{ s.name }} S{{ '%02d' % p.season }}E{{ '%02d' % p.episode }}.{{ job.input.data.extension }}
```

### 7.3 Yazdırma (Log)

```yaml
tasker:
  tasks:
    - name: log_result
      type: print
      template: |
        {% set m = job.plugins.tmdb.movie %}
        {% if m %}
        ✅ {{ m.title }} ({{ m.release_date[:4] }})
        Rating: {{ m.vote_average }}/10
        Genres: {{ m.genres | join(', ') }}
        {% else %}
        ❌ Film bulunamadı: {{ job.input.data.filename }}
        {% endif %}
```

### 7.4 Dinamik Koşul

```yaml
tasker:
  tasks:
    - name: high_quality_only
      type: save
      condition: |
        {% set video = job.plugins.ffprobe.video %}
        {{ video.height >= 1080 and video.hdr }}
      template: |
        {{ config.archive_path }}/4K_HDR/{{ m.title }}.mkv
```

---

## 8. STRING FORMATLAMA

### 8.1 Padding (Sıfır Ekleme)

```jinja2
{{ season | string | zfill(2) }}          {# "1" → "01" #}
{{ '%02d' % episode }}                     {# Python style #}
{{ episode | format('02d') }}              {# Alternatif #}
```

### 8.2 String Birleştirme

```jinja2
{{ title ~ ' (' ~ year ~ ')' }}           {# Tilde ile #}
{{ "%s (%s)" % (title, year) }}           {# Format ile #}
```

### 8.3 String Slicing

```jinja2
{{ release_date[:4] }}                    {# İlk 4 karakter (yıl) #}
{{ filename[:-4] }}                       {# Son 4 hariç (ext kaldır) #}
{{ path.split('/')[-1] }}                 {# Son segment #}
```

---

## 9. HATA AYIKLAMA

### 9.1 Debug Print

```jinja2
{# Değişken içeriğini göster #}
{{ job.plugins | pprint }}

{# Tip kontrolü #}
{{ job.plugins.tmdb.movie.__class__.__name__ }}
```

### 9.2 Güvenli Erişim

```jinja2
{# None hatası almamak için #}
{{ m.title if m else 'Bilinmeyen' }}
{{ (m or {}).get('title', 'Bilinmeyen') }}
```

---

## 10. ÖNEMLİ NOTLAR

1. **Whitespace Kontrolü:** `{%-` ve `-%}` ile boşlukları kaldırabilirsiniz
   ```jinja2
   {%- if condition -%}
   içerik
   {%- endif -%}
   ```

2. **Escape:** HTML için `{{ value | e }}`, URL için `{{ value | urlencode }}`

3. **Raw Block:** Jinja2 yorumlamasını engellemek için:
   ```jinja2
   {% raw %}{{ bu render edilmez }}{% endraw %}
   ```

4. **Macro (Fonksiyon):**
   ```jinja2
   {% macro format_title(m) %}
     {{ m.title }} ({{ m.release_date[:4] }})
   {% endmacro %}
   
   {{ format_title(movie) }}
   ```

---

**Son Güncelleme:** 2025-12-04
