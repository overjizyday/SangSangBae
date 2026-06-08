param(
    [string]$SourcePath = "afc_association_ranking_east_west_points.csv",
    [string]$EastOutPath = "afc_association_ranking_east_points.csv",
    [string]$WestOutPath = "afc_association_ranking_west_points.csv",
    [int]$Seed = 1972
)

$countryMap = @{
    'Saudi Arabia' = '사우디아라비아'
    'Qatar' = '카타르'
    'United Arab Emirates' = '아랍에미리트'
    'Iran' = '이란'
    'Iraq' = '이라크'
    'Uzbekistan' = '우즈베키스탄'
    'Jordan' = '요르단'
    'Oman' = '오만'
    'Kuwait' = '쿠웨이트'
    'Bahrain' = '바레인'
    'Syria' = '시리아'
    'Palestine' = '팔레스타인'
    'Lebanon' = '레바논'
    'Yemen' = '예멘'
    'Turkmenistan' = '투르크메니스탄'
    'Tajikistan' = '타지키스탄'
    'Kazakhstan' = '카자흐스탄'
    'Afghanistan' = '아프가니스탄'
    'Maldives' = '몰디브'
    'Nepal' = '네팔'
    'Sri Lanka' = '스리랑카'
    'Bangladesh' = '방글라데시'
    'Kyrgyzstan' = '키르기스스탄'
    'Japan' = '일본'
    'Korea Republic' = '대한민국'
    'China PR' = '중국'
    'Australia' = '호주'
    'Indonesia' = '인도네시아'
    'Malaysia' = '말레이시아'
    'Thailand' = '태국'
    'Vietnam' = '베트남'
    'Philippines' = '필리핀'
    'Singapore' = '싱가포르'
    'Hong Kong' = '홍콩'
    'Chinese Taipei' = '중화 타이베이'
    'Myanmar' = '미얀마'
    'Cambodia' = '캄보디아'
    'Laos' = '라오스'
    'Brunei' = '브루나이'
    'North Korea' = '북한'
    'India' = '인도'
    'Pakistan' = '파키스탄'
    'Bhutan' = '부탄'
    'Mongolia' = '몽골'
    'Macau' = '마카오'
    'Timor-Leste' = '동티모르'
    'Guam' = '괌'
    'Northern Mariana Islands' = '북마리아나 제도'
}

$rng = [System.Random]::new($Seed)
$source = Import-Csv -Path $SourcePath

function Convert-Row {
    param(
        [pscustomobject]$Row,
        [string]$CountryColumn,
        [string]$CodeColumn,
        [string]$PointsColumn
    )

    $base = [double]$Row.$PointsColumn
    $delta = $rng.Next(-5, 6)
    [pscustomobject]@{
        slot_letter = $Row.slot_letter
        country = $countryMap[$Row.$CountryColumn]
        code = $Row.$CodeColumn
        base_points = [math]::Round($base, 3)
        point_delta = $delta
        points = [math]::Round($base + $delta, 3)
    }
}

$eastRows = foreach ($row in $source) {
    Convert-Row -Row $row -CountryColumn 'east_country' -CodeColumn 'east_code' -PointsColumn 'east_points'
}

$westRows = foreach ($row in $source) {
    Convert-Row -Row $row -CountryColumn 'west_country' -CodeColumn 'west_code' -PointsColumn 'west_points'
}

$eastRows | Export-Csv -Path $EastOutPath -NoTypeInformation -Encoding utf8
$westRows | Export-Csv -Path $WestOutPath -NoTypeInformation -Encoding utf8
